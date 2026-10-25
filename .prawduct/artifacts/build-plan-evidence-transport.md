---
artifact: build-plan
version: 2
scope: evidence-transport
branch: feature/1052-evidence-transport
base: develop
working-branches: []
partition: >-
  01 and 04 start together, isolated worktrees, disjoint files — 01 (delegate K): new
  plugin/lib/evidence_notes.py, evidence.py's envelope append, critic_consolidate.py's note
  hook-in, the hook's `evidence ingest` and the chunk-imported writer's hook-in; 04 (delegate C):
  new plugin/lib/plan_lifecycle.py and plan_status.py's rendering. 01 is reviewed `final` before
  02 and 03 are briefed against its signature. Then 02 (delegate A: plugin/lib/evidence_sync.py,
  `evidence sync|configure` in the hook, the egress records), 03 (delegate B: cmd_clear's ingest
  step, the PR/doctor/onboard skills, `plan status` lifecycle wiring from 04's signature) and 05
  (delegate D: prose — methodology, docs, artifacts, the fragment) in isolated worktrees. The
  hook binary is B's in 02–05 (A hands its two subcommands to B as functions in evidence_sync.py
  and B registers them). The coordinator owns integration, 06 and every governance act.
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only ledger, no model in a fact's write path → conforms: ingest appends code-written lines verbatim; nothing is re-derived"
      - "facts immutable and append-only → conforms: a note is only appended to, a merge only adds lines, ingest only appends"
      - "derived views never feed a gate → conforms: no gate reads a note; gates read the store, which ingest feeds"
      - "a governance document reaches a terminal state, never deleted → inapplicable because this wave archives nothing; plan_lifecycle reads the archive stamp and writes none"
      - "every backlog issue conforms to the title standard → inapplicable because the only items this wave files (Chunk 06) go through the backlog skill, which owns the rule"
      - "a newer-schema fact is a loud block, never dropped → conforms: a schema-ahead line is ingested verbatim so the existing block fires in the receiving clone"
      - "two stores, two lifetimes → conforms: transported facts are shared answers; the store stays per clone and gitignored; nothing per-clone enters the ref"
      - "backlog_service_repo selects the backlog store → inapplicable because no backlog read changes"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms once Chunk 05 narrows the Critic skill's `evidence*` grant to `status`/`list`: `evidence ingest` is a store write the reviewer must not reach"
      - "authority fails closed; advice fails soft → conforms: unreadable notes ingest nothing and say so; a missing tree is a gap; session-start ingest failing is a NOTE"
      - "local-first, three network surfaces → conforms with a recorded site: the notes push/fetch reaches only the product's own remote inside /prawduct:pr (the git-tidy precedent); the commit status is cut pending an owner ruling"
      - "writes nothing into a governed repo except .prawduct/, the store and the reconciled files → conforms read as the store's class, recorded for veto: refs/notes/prawduct and two .git/config keys live inside .git, never the work tree, written only by `evidence configure --apply`"
      - "never specific to Python → inapplicable because nothing here dispatches by language"
      - "guides and reviews, never implements; writes no product config → conforms: the clone's .git/config keys are governance state the plugin itself reads, not the product's configuration"
      - "goals and verification bind; prescribed method is advice → conforms: `cat_sort_uniq` over the design's `union` is method; the goal (every line survives a merge) is pinned by test"
      - "every fact has one home → conforms: `evidence.review_anchor`, `evidence.envelope_line`, `plan_lifecycle.observe`; `check-claims` moves onto `observe` in Chunk 03"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the store independently schema-versioned → conforms: no schema bump (the envelope is unchanged); the note carries the same versioned lines"
      - "exit codes are the contract; attributed errors → conforms: `evidence ingest` 0/1, `sync` 0/1 naming the step/2, `configure` 0/1/2, recorded in api-contract.md by Chunk 05"
      - "additive-first evolution → conforms: new subcommands, one new flag (`plan status --probe-pr`), new keys (`lifecycle`, `evidence`); nothing repurposed"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: one keystone final (redirected to cumulative by a clean tree), one boundary cumulative; 02–05 fold into it"
      - "proportionality ratchets both ways; a control names and emits its yield → conforms: the one new control, `evidence status`'s count of transported facts lacking a note (Chunk 02), is its own observable yield"
      - "state-file growth is an advisory, never a hard block → conforms: the notes ref grows by at most one note per reviewed commit, bounded by the branch's commits a bounded ingest walks; ingested lines fall under the store's existing size probes; no new block"
      - "review rigor is stage-keyed → conforms: inner-stage findings were reported as observations; the boundary cumulative runs everything"
depends_on:
  - documentation/issues/1050-requirements.md
  - documentation/issues/1050-design.md
  - .prawduct/artifacts/build-plan-chunk-status.md
last_validated: 2026-10-25
---

## Goals

**Response taken:** Proceed, citing #1052 (`stage: design`, child of #1050) and
`documentation/issues/1050-design.md` § 4 and § 5 (requirements EV1, EV2, LC1, LC2, NF1). Waves
1 and 2 merged to develop on 2026-10-25, which this wave requires. Delegation for the #1050 waves
was approved by the owner on 2026-10-24 (handoff), so no approval ask is made. Two inferences
below depart from the design's letter and are marked for veto.

**Product:** A second clone of a governed repo — a teammate's machine, CI, a fresh checkout after
a disk wipe — reaches the same coverage verdict for a branch as the clone that ran the reviews,
from the same facts. Today the evidence store lives inside `.git` and is never pushed, so every
other clone sees zero coverage, and since Wave 2 derives chunk status from those facts that gap
is load-bearing. A plan's lifecycle (in progress, merged and awaiting release, released,
superseded) is reported from what git and the change record already show, stored nowhere. This
closes #1052 and, as its last child, #1050.

**Architecture:** The transport is a git-native ref, `refs/notes/prawduct`, carrying the store's
own line format so a note *is* store lines on a commit and ingestion is `append` with
dedup — nothing new to parse, nothing re-derived (`data-model.md`: facts immutable; `architecture.md`:
the git object database is the substrate). Verdicts keep composing by tree id from the store;
the note's commit is a locator only, so squash and rebase lose no branch-time verdict (EV1).
Network happens only where a person acts — `/prawduct:pr create|update` already pushes the
branch, and the notes ride that same act through one hook command; session start and every gate
stay offline (NF1, local-first). Authority fails closed: a note that cannot be read ingests
nothing and says so; a tree another clone does not hold reads as a gap there, never as covered.
Additive-first: new subcommands (`evidence ingest|sync|configure`), new `--json` keys
(`lifecycle`), one new flag on `plan status`; nothing repurposed.

**Constraints and tradeoffs accepted:**
- *Facts carry tree ids, not trees.* A `chunk`/`final` review of a dirty tree records a
  `head_tree` no commit holds; the note transports the fact, and a second clone that lacks the
  tree sees the interval as a gap (`evidence.missing_objects` already names it, as it does after
  a rebase today). The boundary `cumulative` and every committed-delta `verify-resolutions`
  record committed trees, which the branch push carries — so the PR gate's verdict is identical
  across clones. *Inferred, owner can veto:* the design summary's "carrying the reviewed trees"
  is met by the ids; pushing uncommitted trees would need refs to orphan commits and is
  scope-out. Revisit if a consumer needs a mid-chunk review visible in CI.
- *`--github-status` is cut from this wave.* `architecture.md`'s local-first norm says no review
  verdict crosses the network on any surface, and a `prawduct/critic` commit status is exactly
  that verdict leaving through `gh`. Admitting it is an owner ruling on a norm, not a build
  decision; filed as a backlog item in Chunk 06 with the ruling it needs. Nothing else in § 4
  depends on it.
- *Lifecycle is offline first.* `plan status` derives lifecycle from local refs, review-fact
  anchors and the change record; the `gh pr list` fallback the design names for squash/rebase
  consumers runs only behind an explicit `--probe-pr` flag, never from the briefing or a hook
  (NF1; the Stop hook's one network probe is already a known cost). "Released" is answered by the
  change record (`plan_backfill.shipped_scopes`, the release cut's own output) rather than by tag
  containment — the record is the release's home and needs no tag walk. *Inferred:* tags are a
  cross-check the owner may want later; not built.
- *`chunk-imported` facts travel too.* The design transports only the verdict kinds; the Wave 2
  caveat in `doctor` check #23 ("facts live in this clone until #1052") exists because an import
  in clone X is invisible in clone Y, and that stays true unless the imported facts ride the ref.
  An import is anchored on the HEAD at import time (its block-removal commit is that commit's
  child, so the anchor stays reachable). *Inferred, owner can veto — and the window closes at the
  first push of the ref, which happens only inside `/prawduct:pr create`, an act the owner asks
  for; a merged note is never un-merged.* The `--remove-block` flag's retirement stays with #1055
  (a flag removal is not additive).
- *Notes merge by `cat_sort_uniq`, not `union`.* Both are correct under id-dedup; `cat_sort_uniq`
  also drops the blank separator lines `notes append` inserts (probed 2026-10-25, git 2.54) and
  never conflicts. Method, not goal (`architecture.md`: prescribed method is advice).
- *The fetch target is a tracking ref.* `refs/notes/origin/prawduct` receives the remote's notes;
  the local `refs/notes/prawduct` is merged from it and pushed. Fetching straight into the local
  ref would need `+` and would overwrite notes not yet pushed (probed: an unmerged push is
  rejected non-fast-forward, which is the safety the tracking ref preserves).
- *`.git/config` writes* (`remote.<r>.fetch` refspec, `notes.rewriteRef`) are the clone's own
  state, the same class as the store (inside `.git`, never committed), written only by
  `evidence configure --apply`, which `doctor` offers and `onboard` runs. Recorded under the
  "writes nothing except" norm below for veto.
- *Scope not taken:* `.critic-findings.json` survives (Q1): `verify-resolutions` finds its prior
  review through that cache, so a verify dispatched in a second clone has no anchor — filed as a
  follow-up in Chunk 06, not built here. Tag containment, orphan-tree transport, enforcing
  merge-only, and #1055's shim retirements are out.

**Decisions made mid-build:** (appended while building)
- Chunk 04 as built (delegate C, 2026-10-25), accepted by the coordinator: the review-fact
  anchor rule (`head_commit or dispatch_commit`) becomes public `plan_status.review_anchor(body)`
  with `chunk_states` calling it — the inventory found it inline at three sites, and Chunk 01's
  note anchor is a fourth reader; the other two sites move onto it at integration (one home).
  The merged check is two `for-each-ref` calls (branch and base refs, local and every remote;
  `--contains <tip>` over the base refs found), not one `--is-ancestor`, so a merge visible only
  on `origin/<base>` before a pull counts and "base missing" is `unknown`, not "not merged".
  `merged_pr_for(project_dir, branch, sha=None)` answers from `--head <branch>` alone when the
  branch is gone. Three holes in the Goals' lifecycle rule, found by C and sent back as one
  round: a shipped scope with a newer pending fragment is not `released` (step 2 skips scopes
  `pending_scopes` lists); an anchor equal to the fact's own `base_commit` is the fork point and
  certifies no merge; a branch whose tip equals the base tip has no commits of its own and reads
  `in-progress` unless an anchor certifies a fast-forward merge. Settled by LC1 (derived from
  what is observed) and "authority fails closed". Carried to Chunk 02 (A): `plan status
  --probe-pr` reaches `git_hygiene.merged_pr_for`'s `gh pr list`, so the `egress_boundary` entry
  for that site names both callers.
- Chunk 01 as built (delegate K, 2026-10-25, merged 2ab29b00), accepted: `evidence ingest` is a
  data-plane write and is refused from a scratch worktree (the brief's call; the plan's "runs
  anywhere" entry is withdrawn — the store is clone-wide and the main checkout's session start
  ingests); the bound includes the merge base itself (a branch's first dirty-tree review anchors
  on the commit it was cut from — excluding it drops every branch's first round; pinned);
  ingest takes only `TRANSPORTED_KINDS` from schema-supported lines and every schema-ahead line
  whatever its kind, deduping against `facts` and `schema_ahead` both; `evidence.envelope_line`
  is the one owner of the line format and `append_fact` returns the envelope it wrote; the note
  is fed on stdin (`-F -`); at consolidation only an attach `error` prints a NOTE, the import
  writer NOTEs anything but `attached`. Known and accepted: `git notes append` accepts a
  well-formed id the clone does not hold, so `attach` relies on consolidation anchors being real
  commits; a clone with no committer identity cannot write notes and gets a NOTE. Integration
  (coordinator): both delegates wrote a `review_anchor` — the one home is now
  `evidence.review_anchor`, read by `plan_status`, `plan_lifecycle`, `critic_consolidate` (two
  sites, which pass the anchor into `attach`) and `coverage.count_branch_rounds`. Carried to 03 (B):
  `plan import-status`'s docstring and output still say "per-clone until #1052"; the ephemeral
  refusal wording ("discarded") is inaccurate for a store write. Carried to 05 (D): the Critic
  skill's `Bash(prawduct-hook evidence*)` grant now covers a write — narrow it to `status`/`list`.
- Chunk 02 as built (delegate A, 2026-10-25, merged 082fa0ab), accepted: reconcile and the
  unsent-facts count live in `evidence_notes` (one predicate for `evidence status` and `sync`);
  `attach` takes `str | None` and skips `None`; sync runs git with `LC_ALL=C` and
  `GIT_TERMINAL_PROMPT=0` (detectable "couldn't find remote ref"; a credential prompt fails
  instead of waiting out the floor); git does not refuse a new notes merge over an unfinished
  one (probed), so the stuck-merge check is ours via `rev-parse --git-path`; `configure` uses
  `config --add` so a foreign `notes.rewriteRef` survives; a `chunk-imported` fact records no
  anchor, so reconcile counts it as this branch's by `actor.branch` and re-attaches on HEAD; the
  egress record states that notes carry product content (finding text, paths) to the product's
  own remote. The disposition tool refuses `--fixed` on judgeable paths, so R-3/R-8/R-9/R-10/R-11
  are recorded by the verify pass at Chunk 06, not at merge.
- Chunk 05 as built (delegate D, 2026-10-25, merged 33585bd6), accepted: six budget ceilings
  raised, none lowered, each declared in its test with the reason (`review-cycle.md` +68 tokens,
  which no review mode loads; the Critic skill and its three payloads +12, the narrowed grant
  line); a second `[DECISION]` record beneath the "writes nothing into a governed repo" norm for
  the notes ref and the two config keys; R-16's instrument `tests/test_skill_command_grants.py`
  reads the hook's data-plane tables and sweeps every skill and agent grant, one reasoned exemption
  (janitor's `python3 *`, human-invoked). Corrections the coordinator made from D's seams: ingest
  reads the fetched tracking ref too (97cb5fb8 — "refspec plus fetch is not enough" was true and
  is now false; three sentences re-said); Chunk 02's acceptance clause "the Critic's
  infrastructure-coherence check finds the record" names a check no Critic file carries — struck,
  the record's two homes are the acceptance. Carried to 06: `stats`/`contribute` now count
  ingested reviews, so two contributing clones double-count at the collector (backlog item); the
  narrowed `evidence status|list` grants carry no instruction in the Critic's files (kept; ~12
  tokens per run — a later trim if nothing ever uses them); `test-evidence record` is absent from
  the hook's data-plane tables so R-16's sweep does not cover it (observation, not changed here).
- Chunk 03 as built (delegate B, 2026-10-25, merged 0e3a447a), accepted: the session-start line
  says "evidence fact(s)" (resolutions and imports travel too); doctor #25 is a recommendation,
  not a conformance check (`/prawduct:pr` syncs either way); the import writer NOTEs on
  `not in ("attached", "present")` (a `skipped` there means HEAD gave no anchor); R-6's
  TYPE_CHECKING guard in `plan_status` is kept with its comment corrected — the premise that the
  dead import alone justified it was wrong (`plan_lifecycle → release_readiness → gates →
  plan_status` is a real top-level path, traced by AST), the dead import itself is gone;
  `check-claims` prints each non-release-pending miss as `not release-pending (<state>: <reason>)`
  and a `working-branches:` entry missing while the integration branch is in progress is now
  `missing`; doctor's numbering keeps the retired #13 gap. Session start on a foreign binary now
  writes the store (ingest) under the standing harness-invoked exemption.
- **Chunk 06 live verification, 2026-10-25** (`tools/evidence-roundtrip.sh <repo>
  feature/1052-evidence-transport <scratch>`, nothing leaves the machine): clone X with this
  repo's store copied in — `evidence status` → "no refs/notes/prawduct … none of the store's
  transported facts is on a note"; `evidence sync` → `reconciled: 1, pushed: true` (the keystone
  review the `-live` consolidator never noted, attached by reconcile); clone Y from the mirror,
  empty store — `check-cumulative-critic` → uncovered, "no review round recorded"; `evidence sync`
  → `ingested: 1`; `check-cumulative-critic` → the same verdict X prints, word for word ("1 review
  round since the merge-base", uncovered at the moved HEAD); `evidence list` shows
  `rev-20261025T173802Z-7a0e5c49`. Acceptance met. `plan status` on this branch prints
  `lifecycle: in-progress`; `check-claims` names all three retained plans `merged-unreleased` by
  anchor, exit 0.

**Level:** High for § 4's writer, reader and sync (every store writer, the consolidation write
sites, the PR skill's push step and session start's boundary region are enumerated from a
2026-10-25 inventory with line anchors, and git's notes behaviour was probed). Medium for § 5: the
rule for a merged plan whose branch is gone under squash is net new (`unknown` without
`--probe-pr`), and whether consumers accept "released" from the change record alone is an
inference — the cheapest raise is the owner reading the Lifecycle rule in Chunk 04 before C is
briefed, so it is stated there in full.

### Norm reconciliation (`governed_by`)

One disposition per Direction norm lives in the frontmatter's `governed_by:` block (the form
`record-lint`'s governed-by check parses); the four departures worth a reader's eye are the
recorded egress site, the `.git/config` keys, the cut commit status and the Critic grant narrowing.

## Build Chunks

Shapes every chunk reads or writes (fixed here so no delegate guesses them):

- **Note body:** the store's envelope lines, one JSON object per line, exactly the bytes the
  store holds. Readers tolerate blank lines and whitespace. The note hangs on the fact's
  **anchor**: `body.head_commit or body.dispatch_commit` for a `review`; the `verified_by`
  review's anchor for a `resolution`; the HEAD at write time for a `chunk-imported`.
  `TRANSPORTED_KINDS = frozenset({"review", "resolution", "chunk-imported"})`.
- **Refs:** local `NOTES_REF = "refs/notes/prawduct"`; tracking
  `NOTES_TRACKING_REF = "refs/notes/origin/prawduct"` (the remote name substituted from
  `gitstate.push_remote`); refspec `+refs/notes/prawduct:refs/notes/<remote>/prawduct`; config
  `notes.rewriteRef = refs/notes/prawduct`.
- **`evidence_notes` signature** (Chunk 01, reviewed before 02/03 are briefed):
  `attach(project_dir, envelope: dict, anchor: str) -> dict` (`{"status": "attached"|"skipped"|"error", "reason"}`;
  skipped when the kind is not transported or the anchor is not an object id);
  `ingest(project_dir, *, bound: bool = True, known=None) -> dict`
  (`{"status": "ok"|"error", "appended": int, "seen": int, "commits": int, "reason"}`; bounded
  means commits in `merge_base..HEAD` from `coverage.resolve_merge_base_tree`, unbounded walks
  every note; `known` is a `read_facts` result to dedupe against, read once when omitted);
  `evidence.append_envelope(project_dir, envelope) -> dict` (verbatim append of a foreign
  envelope: requires `kind`, `id`, int `schema`, dict `body`; refuses nothing else).
- **`plan_lifecycle` signature** (Chunk 04, B wires it in 03):
  `observe(plan_path, *, repo_dir, facts=None, probe_pr=False) -> Lifecycle` with
  `state: Literal["in-progress", "merged-unreleased", "released", "superseded", "unknown"]`,
  `reason: str` (what was observed, one sentence), `released_in: str | None`,
  `probed: bool`.
- **`evidence_sync` signature** (Chunk 02): `sync(project_dir, *, push: bool = True) -> dict`
  (`{"status": "ok"|"error", "step": "fetch"|"merge"|"ingest"|"push"|None, "pushed": bool,
  "ingested": int, "reason"}`); `configure(project_dir, *, apply: bool) -> dict`
  (`{"status": "ok"|"error", "changes": [..], "applied": bool, "reason"}`).

### Chunk 01: notes written at consolidation, read back by `evidence ingest`

- **Description:** New module `plugin/lib/evidence_notes.py` as the signature above. `attach`
  runs `git notes --ref prawduct append -F <tmpfile> <anchor>` through `evidence.run_git` with
  the envelope serialised exactly as the store line. `ingest` lists notes once
  (`git notes --ref prawduct list`), intersects with the bounded commit set (`git rev-list
  merge_base..HEAD`, one call; none when unbounded), reads every matching note blob in one
  `git cat-file --batch`, parses lines, drops `(kind, id)` pairs already in the store, and appends
  the rest through `append_envelope`. No notes ref → `{"status": "ok", "appended": 0}` with
  **zero further subprocesses** after the one `rev-parse -q --verify refs/notes/prawduct`.
  Hook-ins: `critic_consolidate.consolidate` calls `attach` after each successful `review` and
  `resolution` append (the two write sites at `critic_consolidate.py` ≈5874 and ≈5896 — a
  failed attach is a NOTE on stderr, never a failed consolidation); the hook's `chunk-imported`
  writer (`prawduct-hook` ≈7827) attaches on HEAD. New `prawduct-hook evidence ingest [--all]
  [--json]` (a data-plane write: refused from a scratch worktree and on a foreign binary; the
  main checkout's session start ingests for the whole clone) prints appended/seen/commits.
- **Depends on:** none
- **Artifacts consumed:** `1050-design.md` § 4; `plugin/lib/evidence.py` (`append_fact`,
  `read_facts`'s `(kind, id)` dedup, `run_git`, `missing_objects`); `plugin/lib/critic_consolidate.py`
  write sites; `plugin/lib/coverage.py` `resolve_merge_base_tree`; `plugin/lib/gitstate.py`
  `is_object_id`; `tests/test_plan_status.py`'s `repo` fixture and `tests/test_git_hygiene.py`'s
  `clone` fixture (bare origin) as the shapes to copy.
- **Deliverables:** new `plugin/lib/evidence_notes.py`; `append_envelope` and `TRANSPORTED_KINDS`
  in `plugin/lib/evidence.py`; the two `attach` calls in `plugin/lib/critic_consolidate.py`; the
  import writer's `attach` and `evidence ingest` in `plugin/bin/prawduct-hook`;
  new `tests/test_evidence_notes.py` covering, red first: a review fact appended at consolidation
  leaves one note on its anchor holding the identical line; a resolution's note lands on its
  `verified_by` review's anchor; a dirty-tree review (`head_commit` null) anchors on
  `dispatch_commit`; a `session-start` fact attaches nothing; a store wiped and re-ingested from
  notes yields the same `(kind, id)` set and an identical `coverage_verdict` for a committed
  interval; ingest twice appends nothing the second time; a note on a commit outside
  `merge_base..HEAD` is ignored when bounded and read with `--all`; a blank-separated note body
  ingests every record; a schema-ahead line is appended verbatim and `read_facts` files it under
  `schema_ahead`; a malformed line is skipped with its count in `reason` and the rest ingested;
  no notes ref costs exactly one subprocess (spy, by call); a bare-origin round trip — clone A
  consolidates and pushes `refs/notes/prawduct`, clone B fetches and ingests — reaches the same
  verdict for the committed interval.
- **Tests:** the module above; `tests/test_critic_consolidate.py` gains the attach-on-append case
  and the attach-fails-softly case.
- **Acceptance criteria:** every listed shape has a red-first test; `attach` and `ingest` make no
  network call (spy on `socket` and on `run_git`'s argv for `fetch|push|ls-remote|pull`);
  `critic_consolidate`'s store append succeeds whether or not the note does; on this repo
  `python3 plugin/bin/prawduct-hook evidence ingest` exits 0 and appends 0 (no ref yet).
- **Critic mode:** final
  <!-- Keystone: 02 and 03 build on this signature and on the note body shape. -->
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass (the delegate's ceiling)
  2. Handed back; the coordinator merges and runs `/prawduct:critic` — blocking findings resolved
  3. Committed — then 02 and 03 are briefed against the signature above

### Chunk 02: `evidence sync` and `evidence configure`

- **Description:** New module `plugin/lib/evidence_sync.py`. `sync`: `git fetch <remote>
  +refs/notes/prawduct:refs/notes/<remote>/prawduct` (a missing remote ref is not an error — a
  first push has nothing to fetch), `git notes --ref prawduct merge -s cat_sort_uniq
  <remote>/prawduct` when the tracking ref exists, `evidence_notes.ingest` (bounded), then
  `git push <remote> refs/notes/prawduct` unless `push=False`; a rejected push, a stuck
  `NOTES_MERGE_REF` from an earlier failure, or git failing are reported with the failing `step`
  and git's stderr scrubbed through `git_hygiene`'s denylist, nothing retried. `configure`: adds
  the fetch refspec to `remote.<remote>.fetch` if absent and sets `notes.rewriteRef`; preview by
  default, `--apply` writes; no remote → `ok` with the reason and nothing to do. Both are
  reached only when a person or the agent runs the command — the same class as `git-tidy`'s
  fetch and push — and the egress record says so: `project-state.yaml` `egress_boundary` gains
  the site, `security-model.md`'s egress enumeration gains the matching line. **Reconciliation (keystone review R-3/R-11):** a fact whose
  note was never written must be findable and re-sendable from the clone that holds it.
  `evidence_notes.attach` becomes idempotent (no-op when the anchor's note already holds the
  line) and `critic_consolidate` calls it on every path, the already-appended retry paths
  included; `sync` runs a `reconcile` step before the push — every transported fact in the store
  whose anchor is in the bound gets its line attached if missing — and `evidence status` prints
  one durable line, `N transported fact(s) with no note on their commit`, so the loss is visible
  outside the act that caused it. Also A's: R-8 (`evidence.py`'s CLI header still presents
  `evidence*` as read-only), R-9's `evidence_notes` docstring, R-10 (blank-line residue;
  `attach`'s `anchor: str` annotation against `None`-passing callers). The two hook
  subcommands are *functions* here (`cmd_evidence_sync(project_dir, args)`,
  `cmd_evidence_configure(project_dir, args)` returning an exit code); B registers them in the
  hook in Chunk 03 (exit 0 ok, 1 a reported failure naming the step, 2 usage).
- **Depends on:** Chunk 01
- **Artifacts consumed:** `1050-design.md` § 4 "Transport"; `plugin/lib/git_hygiene.py`
  (`_git_write`, the stderr scrub, `_gh_timeout`'s network budget);
  `plugin/lib/evidence.py` `run_git` (`NETWORK_TIMEOUT_FLOOR` applies to fetch/push);
  `plugin/lib/gitstate.py` `push_remote`; `tests/test_git_hygiene_merge.py`'s second-clone setup.
- **Deliverables:** new `plugin/lib/evidence_sync.py`; the `egress_boundary` line in
  `.prawduct/project-state.yaml` and the enumeration line in `.prawduct/artifacts/security-model.md`;
  new `tests/test_evidence_sync.py` covering, red first: first sync with no remote notes pushes
  and reports `pushed`; two clones appending different notes on the same commit both sync and
  each ends with both records, once; a clone behind the remote fetches, merges, ingests and its
  store gains the other clone's facts; `push=False` pushes nothing; a remote that rejects the push
  reports `step: push` and the local ref is intact; a stuck merge state reports `step: merge`;
  `configure` preview writes nothing, `--apply` writes both keys, a second `--apply` changes
  nothing, and a repo with no remote reports that; after `configure --apply`, a plain
  `git fetch` carries the notes (probed 2026-10-25).
- **Tests:** as above.
- **Acceptance criteria:** every network call goes through `run_git` (spy on argv; the timeout
  floor applies); no `gh` call anywhere in the module; the egress record names the site in both
  homes (`project-state.yaml` `egress_boundary` and `security-model.md`).
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass
  2. Handed back; merged and reviewed with 03–05 in Chunk 06's cumulative
  3. Committed

### Chunk 03: hook and skills — session-start ingest, PR push, doctor and onboard, lifecycle wiring

- **Description:** In `plugin/bin/prawduct-hook`: `cmd_clear`'s boundary region (beside
  `_record_session_start`, boundary only, never `--brief-only`) calls `evidence_notes.ingest`
  bounded, failing soft with a NOTE and printing one line only when something was appended
  (`N review facts ingested from refs/notes/prawduct`); registers `evidence sync` and
  `evidence configure` from Chunk 02 (`_reject_unknown_args`, the data-plane/read-only tables as
  each command's writes require); `plan status` prints a `lifecycle:` line from
  `plan_lifecycle.observe` and `--json` gains `lifecycle: {state, reason, released_in, probed}`,
  with a new `--probe-pr` flag passed through; `plan check-claims`' release-pending outcome
  reads `observe(...).state == "merged-unreleased"` instead of its private
  `_release_pending_records` (deleted). Skills: `pr/SKILL.md` Create step 5 and Update step 1
  run `prawduct-hook evidence sync` after the branch push and before `check-branch-pushed` (a
  failure is reported, never blocks the PR — coverage is the PR gate, transport is not), with the
  `allowed-tools` grant; `doctor/SKILL.md` gains check #25 (notes transport unconfigured →
  offer `evidence configure --apply`) and rewrites #23's caveat (imports now travel; the offer
  passes `--remove-block`); `onboard/SKILL.md` runs `evidence configure --apply` after its commit
  when a remote exists. Also B's, from the keystone review: R-2 (pin the skew guard's refusal of
  `evidence ingest` at `_dispatch`'s argv wiring in `tests/test_binary_skew_guard.py`, with
  `evidence status` as the proceeding control); R-6 (delete `plan_lifecycle`'s dead
  `plan_status` import, and the TYPE_CHECKING cycle workaround in `plan_status` it alone
  justified); R-7 (one per-op read table for `evidence` from which both the ephemeral and the
  skew guard derive — `sync` and `configure` are writes on both sides by construction — and the
  ephemeral refusal's reason stated at the branch: the store cannot strand, the refusal keeps a
  scratch tree from racing the main checkout's ingest); R-9's `plan_lifecycle` docstring; the
  `plan import-status` docstring and output that still say "per-clone until #1052".
- **Depends on:** Chunks 01, 02 (signatures); 04's signature (fixed above, wired here)
- **Artifacts consumed:** `1050-design.md` § 4 "Transport", § 5; `plugin/bin/prawduct-hook`
  (`cmd_clear` ≈1950, `_cmd_plan_status`, `_cmd_plan_check_claims`, `_release_pending_records`,
  the ops tables); `plugin/skills/pr/SKILL.md`; `plugin/skills/doctor/SKILL.md`;
  `plugin/skills/onboard/SKILL.md`; `plugin/lib/briefing.py` `_spawn_cache_warm` (the prior art
  for paying nothing at session start — ingest is synchronous because the briefing reads the
  store next, and bounded so the cost is the branch's commits).
- **Deliverables:** the changes above; `tests/test_hook_cli_regressions.py` or
  a new `tests/test_session_start_ingest.py` covering: boundary start ingests and prints the count,
  `--brief-only` ingests nothing, no notes ref costs one subprocess beyond today's (extend
  `tests/test_hot_path_git_batching.py`'s count), an unreadable note is a NOTE and the briefing
  still renders; `tests/test_plan_hook_cmd.py` gains the lifecycle line and `--json` key and
  `--probe-pr` pass-through; `tests/test_plan_check_claims.py` renegotiated onto `observe`;
  skill-prose tests that pin the PR skill's step order (push → sync → check-branch-pushed) and
  the doctor check numbering.
- **Tests:** as above.
- **Acceptance criteria:** `grep -n '_release_pending_records' plugin/` returns nothing; session
  start in a repo with no notes ref adds exactly one git call to today's count (pinned);
  `/prawduct:pr`'s prose names `evidence sync` once in each flow; on this branch `plan status`
  prints `lifecycle: in-progress`.
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass
  2. Handed back; merged and reviewed with 02, 04, 05 in Chunk 06's cumulative
  3. Committed

### Chunk 04: lifecycle observed — `plan_lifecycle.observe`

- **Description:** New module `plugin/lib/plan_lifecycle.py`, the one derivation of LC1, as the
  signature above. Rule, in precedence order, each step naming what it observed in `reason`:
  (1) an archived plan → its `lifecycle:` stamp (`superseded` or, for `completed`, `released`
  with `released_in`); (2) the scope is in `plan_backfill.shipped_scopes` over
  `change_log_archive.load_all_text` → `released`, `released_in` from the tag; (3) the plan's
  `branch:` exists locally or as `<remote>/<branch>` and its tip is **not** an ancestor of the
  declared `base:` (`merge-base --is-ancestor`, one call) → `in-progress`; (4) the tip is an
  ancestor → `merged-unreleased`; (5) the branch is gone: the newest review fact for the scope
  whose anchor is an ancestor of `base` → `merged-unreleased` (merge-commit flow); else the
  scope's fragment is pending (`release_readiness.pending_scopes`) → `merged-unreleased` with
  `reason` saying it is inferred from the deleted branch and the pending fragment (the Wave 2
  `check-claims` rule, now one home); (6) otherwise `unknown` naming what was missing — and with
  `probe_pr=True`, step (6) first asks `git_hygiene.merged_pr_for` (made public) and answers
  `merged-unreleased` on a merged PR. `plan_status.render_table` gains nothing; a new
  `plan_status.render_lifecycle(lifecycle) -> str` renders the line B prints. Cost: at most two
  git calls (one `rev-parse` for the branch, one `--is-ancestor`), plus one `--is-ancestor` per
  fact probed in step (5), newest first, stopping at the first hit; no network unless `probe_pr`.
- **Depends on:** none (reads Wave 2's modules; nothing from 01–03)
- **Artifacts consumed:** `1050-design.md` § 5; `plugin/lib/plan_archive.py` (stamps);
  `plugin/lib/plan_backfill.py` `shipped_scopes`; `plugin/lib/change_log_archive.py`;
  `plugin/lib/release_readiness.py` `pending_scopes`; `plugin/lib/plan_status.py` (`_Reachability`,
  the anchor rule); `plugin/lib/git_hygiene.py` `_merged_pr_for` and `tests/test_git_hygiene_merge.py`'s
  `fake_gh`/`serve_merged`; `plugin/lib/work_unit.py` (`base`, `branch` from the plan's
  declarations).
- **Deliverables:** new `plugin/lib/plan_lifecycle.py`; `render_lifecycle` in
  `plugin/lib/plan_status.py`; `merged_pr_for` public in `plugin/lib/git_hygiene.py`;
  new `tests/test_plan_lifecycle.py` covering, red first: a live plan on an unmerged branch →
  `in-progress`; merged with `--no-ff` and the branch kept → `merged-unreleased`; branch deleted
  after a merge commit, a review fact anchored on the branch → `merged-unreleased` by anchor;
  branch deleted, no fact, fragment pending → `merged-unreleased` by inference, reason says so;
  squash-merged and branch deleted, no fragment → `unknown`, and with `probe_pr` against the
  fake `gh` → `merged-unreleased` with `probed: true`; scope shipped in the archive log →
  `released` with `released_in`, even when the branch still exists; an archived plan →
  `superseded`/`released` from the stamp with no git call (spy); no network without `probe_pr`
  (spy); the two-call cost bound for the in-progress case (spy, by call).
- **Tests:** as above; `tests/test_plan_status.py` gains `render_lifecycle`'s one fixture.
- **Acceptance criteria:** `observe` is the only function in `plugin/` returning a lifecycle
  state (grep for the five literals outside this module and `plan_archive`'s stamps); every
  state's `reason` names an observation, never a stored field other than the archive stamp;
  on this repo `observe` over `build-plan-chunk-status.md` answers `merged-unreleased` by anchor
  (its facts are in develop's history) and over `build-plan-work-unit-binding.md` likewise.
- **Done when:**
  1. Acceptance criteria met and the owned test modules pass
  2. Handed back; merged and reviewed with 02, 03, 05 in Chunk 06's cumulative
  3. Committed

### Chunk 05: prose — what the store's reach now is

- **Description:** Every shipped surface that says the store is clone-local and never leaves
  the clone now says what is true: shared by every worktree of a clone, and its verdict kinds
  travel with the branch on `refs/notes/prawduct` when `/prawduct:pr` pushes (ingested at session
  start; `evidence ingest|sync|configure`). Sites from the 2026-10-25 inventory:
  `methodology/building.md` (evidence model paragraph), `skills/critic/review-cycle.md` § evidence
  model, `skills/critic/SKILL.md`, `skills/pr/SKILL.md`'s coverage sentence, `docs/governance-telemetry.md`,
  `docs/project-state-keys.md`, `docs/test-report-contract.md`, `methodology/session-hygiene.md`,
  `skills/migrate/SKILL.md`, `documentation/project-structure.md`, `documentation/MIGRATION.md`,
  and `evidence.append_guard_refusal`'s "neither store answers a cross-CLONE question"
  docstring. Artifacts: `architecture.md`'s descriptive store rows (≈211–217, 255–257) and a
  `[DECISION]` record beneath the local-first norm naming the new egress site and the cut commit
  status; `data-model.md`'s description of the store's reach; `api-contract.md` § Operations
  gains `evidence ingest|sync|configure`, `plan status --probe-pr`, the `lifecycle` key and the
  exit codes Chunks 02/03 documented; `.prawduct/cross-cutting-concerns.md` gains the new
  storage surface's row (how security, observability and error handling land on the notes ref —
  or why not); `build-plan-chunk-status.md`'s consumer-facing "until #1052" sentences are left
  as history (it is a retained, merged plan), but `.prawduct/changes/chunk-status.md`'s
  consumer note, still pending release, is amended to say transport ships in the same release.
  From the keystone review: the Critic skill's
  `Bash(prawduct-hook evidence*)` grant (both binary forms) narrows to `evidence status` and
  `evidence list`, and R-16's missing instrument — a test that no skill's prefix grant covers a
  data-plane write op — lands beside the prose tests. This wave's fragment
  `.prawduct/changes/evidence-transport.md` gets its narrative, `closes:
  [1052, 1050]`, and a consumer note that tells an operator the three commands, that a fresh
  clone needs one `evidence sync` (or a configured refspec) before coverage appears, and that
  mid-chunk reviews of uncommitted trees stay clone-local.
- **Depends on:** Chunks 01, 02, 04 (names and exit codes); runs in parallel with 03 on
  disjoint files (03 owns `plugin/skills/pr/SKILL.md`, `plugin/skills/doctor/SKILL.md` and
  `plugin/skills/onboard/SKILL.md`; 05 owns everything else)
- **Artifacts consumed:** the inventory's § 14 list (above); `plugin/skills/critic/review-cycle.md`;
  `.prawduct/artifacts/api-contract.md`; the budget tests (`tests/test_plugin_methodology_digest.py`
  and the token-footprint pins) — a trim lands under its ceiling, lower the ceiling in the same
  commit.
- **Deliverables:** the edits above; the fragment complete (`change_fragments.validate` clean);
  tests that read prose (`tests/test_*prose*`, the budget tests) green; a grep for `never pushed`,
  `clone-local`, `this clone's evidence store` and `until #1052` across `plugin/` and
  `documentation/` returning only history (CHANGELOG, archived plans, `documentation/issues/`).
- **Tests:** the prose and budget tests; `python3 plugin/bin/prawduct-hook` fragment validation.
- **Type:** doc-only
- **Acceptance criteria:** the grep above; every budget test green with ceilings lowered where a
  trim landed; `api-contract.md` names every new subcommand, flag, key and exit code 02/03 record.
- **Done when:**
  1. Acceptance criteria met and the prose/budget tests pass
  2. Handed back; merged and reviewed with 02–04 in Chunk 06's cumulative
  3. Committed

### Chunk 06: integration, live verification and the boundary review

- **Description:** The coordinator integrates 02–05, runs the declared suite, and verifies the
  acceptance in `#1052` live: a fresh `git clone` of this repo into the scratchpad, `evidence
  sync` (push from this clone first), then `check-cumulative-critic` in the clone reports the
  same verdict as here for this branch. Files two backlog items: `critic-consolidate
  --github-status` with the owner ruling it needs on the local-first norm; Q1 (a
  `verify-resolutions` anchor that does not depend on `.critic-findings.json`, so a verify can
  run in a second clone). Confirms the egress record in both homes and `/prawduct:doctor`'s
  numbering. Then commits and runs the one `/prawduct:critic cumulative`; #1052 and #1050 close
  with the fragment's `closes:` at the PR.
- **Depends on:** Chunks 01–05
- **Artifacts consumed:** this plan's Goals; `documentation/issues/1050-design.md` § 9 (the
  "notes round-trip" and "squash leaves `evidence status` able to list its facts" pins — both
  land in 01/04's tests, verified present here).
- **Deliverables:** the integrated branch; the live verification recorded in this plan's
  Decisions block with the commands run; the two backlog items; `prawduct-hook test-evidence
  record` over the integrated tree.
- **Tests:** the whole declared suite (`test_commands:` in `project-state.yaml`).
- **Acceptance criteria:** the live round trip reaches the same verdict in the clone; the suite
  is green and recorded; the cumulative's blocking findings are zero after one verify round.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the suite recorded green
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** consolidate a review here, open a second clone of this repo, fetch the
notes ref and run `prawduct-hook evidence ingest`, and see the review's facts in `evidence list`.

## Governance Checkpoints

**Commit & PR cadence:** 01 commits after its `final`; 02–05 land as delegate merges and are
reviewed once in 06's `cumulative`, which is the `/prawduct:pr create` gate. One PR for the wave.

- After Chunk 01: the note-body shape and `ingest`'s dedup are what every later chunk trusts —
  the `final` is where a wrong shape is cheapest to change.
- After Chunk 06 (cumulative): the live cross-clone round trip on this repo, and the egress record
  checked against both homes before the PR.
