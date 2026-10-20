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
      - "backlog issues conform to the title standard on every write path → inapplicable because fragments create no backlog issue; the merge-flow close only changes status through /prawduct:backlog, which applies the standard"
  - artifact: architecture
    dispositions:
      - "local-first, stdlib-only governance runtime → conforms: Python stdlib only; changie and towncrier rejected (FRG8)"
      - "reviewer never mutates the session it reviews → inapplicable because no review path writes fragments"
      - "authority fails closed, advice fails soft → conforms: an unreadable or invalid fragment refuses at PR Step 1c and the cut writes nothing on any error; the cut's list of `none:` reasons is advice and blocks nothing"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state and the files it must reconcile → conforms for wave 1: fragments and the archive live under `.prawduct/`, and `plugin/CHANGELOG.md` is written only in prawduct's own repo by its release operator. Wave 2 must re-decide this before the cut writes any consumer repo's digest file"
      - "written in Python, never specific to Python → conforms: the format is Markdown with frontmatter and no reader dispatches by language"
      - "guides and reviews, never implements → conforms: this governs prawduct's own change record and writes no product code"
      - "goals and verification bind, prescribed method is advice → conforms: the schema is what binds; the template's prose is advice"
      - "every fact has one home → conforms: `closes:` is the one home for the closes relation and the fragment's note the one home for consumer text; the PR body's `Closes` lines and the CHANGELOG section are generated from them"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; CLI subcommands internal → conforms: cut-change-log and migrate-change-log join the internal/unstable tier"
      - "exit codes are the contract on a documented scheme, errors attributed with a stable prefix → conforms if Chunks 03 and 04 give cut-change-log and migrate-change-log the existing scheme (0 done, 1 refused with a named reason, 2 usage); checked at those chunks' reviews"
      - "additive-first evolution → conforms: check-change-log-entry keeps every existing verdict name and adds fragment verdicts beside them; no `--json` key is repurposed"
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
- Chunk 01: fragment values are read by `change_fragments`' own parser over the shared block walker
  (`plan_index.frontmatter_span`), not `plan_index`'s value reader. That reader treats any `#` as
  a comment, which would truncate `owner/repo#N`. Settled by `closes:` (owner) and the #790 quoted-`#` precedent.
- Chunk 01: `closes:` accepts only fully qualified spellings: `owner/repo#N` exactly as the
  normalizer renders it, or a markdown `PFX-XXXX` via the existing `ids.is_pfx`. A persisted value
  must resolve without a default repo. Settled by "do it right" for a lock-in format.
- Chunk 01: D5's `unknown-reopen-target` check needs the archive and the pending set, so it lands
  with the readers in Chunk 02, not in the per-file validator. Placement only; the design settled it.
- Chunk 01: the module's surface differs from D1's sketch, which the design now tracks:
  `validate_fragment` returns `Problem(code, detail)` rather than strings, so Step 1c can surface
  codes. `load_pending` returns a `FragmentFile` per file, because readers need the problems of
  invalid files, not only the valid ones. `Fragment` keeps the raw keys, with typed properties,
  because validation must see unknown and duplicate keys. `render_entry(release=)` stamps at
  render, never on the file. `none_reasons` feeds the cut's dry run (owner decision). Settled by
  the readers' needs (Chunks 02–03).

**Level:** High. The design is grounded in the current tree (re-verified 2026-10-19), the July
proposal is reconciled, and every schema decision is the owner's.

## Status

- [x] Chunk 01: Fragment format core — `change_fragments.py`, schema, template
- [ ] Chunk 02: Readers and the PR gate read fragments (dual-shape)
- [ ] Chunk 03: The cut — `cut-change-log`
- [ ] Chunk 04: Prawduct migrates onto fragments; docs and runbooks
Context: Chunk 01 committed (0e374cab) after its chunk review: 0 blocking, 6 observations. Observation
fixes (the `schema: [2]` list bug; design and plan records; a stale `building.md` sentence about
editing during a review) were committed separately after it, and Chunk 02's review covers them.
Next: Chunk 02.
