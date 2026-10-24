---
artifact: build-plan
version: 2
scope: git-hygiene
branch: feature/1041-git-hygiene
depends_on:
  - artifact: architecture
  - artifact: security-model
governed_by:
  # Seeded with `prawduct-hook jurisdiction --artifacts-only` over a paragraph describing
  # #1041, then curated to artifacts whose `## Direction` binds a git-mutating command,
  # an advisory probe, or a new CLI subcommand.
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews -> inapplicable because no
        reviewer path runs git-tidy; it is invoked by the agent or a person."
      - "authority fails closed; advice fails soft -> conforms. The advisory is advice and degrades
        to a named problem. git-tidy's deletions are the authority half: a proof that cannot be
        computed is no proof, so nothing is deleted (R10)."
      - "local-first -> conforms. The advisory makes no network call (asserted by test). git-tidy's
        fetch/push-delete/gh calls go to the product's own remote and carry no product content,
        so they are egress SITES, not a surface (the 2026-09-07 clarification). They are added to
        both site lists in Chunk 03 and reached only when a person or the agent runs the command."
      - "the plugin writes nothing into a governed repo except its own state -> conforms. git-tidy
        deletes git refs and worktrees the operator approved; it writes no file into the tree.
        Refs and worktree admin entries are git metadata the owner's yes covers, not framework
        files."
      - "Python-implemented, never Python-specific -> conforms; git only, no language reading."
      - "prawduct guides and reviews; it never implements -> conforms. This is prawduct's own
        tooling, the norm's stated Scope carve-out; it writes no product code."
      - "goals and verification bind; prescribed method is advice -> conforms. Departures from the
        design's method get recorded below under Decisions made mid-build."
      - "every fact has one home -> conforms. The protocol's home is the requirements doc. The
        mechanism's home is git_hygiene.py's docstring. The PR skill, delegation.md, the digest
        and the janitor theme cite the command and restate none of its rules."
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions -> conforms. Preference rows are read
        through read_preference_row, and an unrecognised value reads as `propose`. Branch names
        reach git as list-form args after `--`/`refs/heads/` qualification, never a shell."
      - "a destructive operation requires operation-level owner approval -> conforms. The dry run
        names every target, the count, and what cannot be undone (a remote delete). `--apply
        <fingerprint>` binds the approval to exactly that set. After-merge cleanup rides the merge
        the owner approved; reap rides the reap delegation.md already prescribes."
      - "a product's content leaves its own repo and owner only through a pinned, owner-approved
        surface -> inapplicable because git-tidy sends no product content anywhere. Its network
        calls delete refs on, and query pull requests in, the product's OWN remote, the repo the
        owner already pushes to, so nothing leaves the repo or its owner. Chunk 03 adds these to the
        egress SITE lists, which are a different inventory from content surfaces."
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 -> inapplicable because no review payload changes."
      - "a control names its yield and emits it -> conforms. Yield: candidates removed. Emission:
        the advisory's evidence count in the advisory store, and git-tidy's per-kind counts."
      - "state-file growth is advisory -> inapplicable because no state file is added."
      - "review rigor is stage-keyed -> inapplicable because no review behaviour changes."
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; no per-subcommand version -> conforms; `--json` carries a
        schema_version like `worktrees --json`."
      - "exit codes are the contract; severity prefixes; no tracebacks -> conforms: 0/1/3 as the
        design states, NOTE:/WARNING: prefixes, errors attributed."
      - "additive-first evolution -> conforms. A new subcommand; no existing flag, exit code or json
        key is repurposed. `worktrees --json` is unchanged."
  - artifact: observability-strategy
    dispositions:
      - "stable severity prefixes; stdout agent channel / stderr user channel -> conforms."
      - "the ledger has a single writer -> inapplicable because nothing is written to the ledger."
      - "text emitted into a governed product names no prawduct-internal identifier -> conforms;
        pinned by test for the advisory's fields and git-tidy's output."
  - artifact: operational-spec
    dispositions:
      - "versioning is conservative -> conforms; a fragment under .prawduct/changes/, patch-level."
      - "gitflow: develop integrates, main holds releases -> conforms, and it is why both are in
        the long-lived set."
partition: serial — every chunk extends plugin/lib/git_hygiene.py, so no two can run apart
last_validated: 2026-10-22
lifecycle: completed
archived: 2026-10-24
released_in: v3.7.2
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Goals

**Response taken:** Asked in one batch. The owner answered the three protocol forks on
2026-10-22 and confirmed R9 the same day. Requirements: `documentation/issues/1041-requirements.md`.
Design: `documentation/issues/1041-design.md`.

**Product:** Developers using prawduct, this repo first. The aim is to keep a clone's branch and
worktree list meaning something: merged work disappears, and what remains is live or needs a
decision. The owner's "lean means out of the developer's way" is the bar: one combined proposal
and one yes, never a stop per branch.

**Architecture:** Deletion happens only on proof (R1–R3, R8). Local-first holds: the session
path makes no network call. One classifier serves the advisory, the command, and later #843's
pushed-branch arm.

**Constraints:** Never `-D`, never `--force` (owner protocol). A locked worktree is the harness's
(design, research). Advisory copy names no internal id (observability norm). The session digest's
10,000-character wall (authoring learnings).

**Tradeoffs accepted:**
- Squash-merge proof checks at most 8 branches per run. Revisit if a repo shows the cap binding.
- An environment branch kept equal to `main` reads as integrated until it is listed in
  `Long-lived branches`. The dry run and the owner's yes guard it, and the dry run names the row.
- The advisory adds about 0.36 s to each session start on this clone (four worktrees, about 40
  refs; measured 2026-10-22). About half of that is the worktree scan the briefing also runs.
  Revisit if a clone with dozens of worktrees makes it felt, by passing the briefing's scan to the
  probe.

**Decisions made mid-build:**
- Chunk 01: a sibling worktree is proposed only when it holds a non-long-lived branch. A
  detached or long-lived-branch checkout is never proposed. Settled by the goal that nothing is
  removed by surprise: `prawduct-live`, the install every governed repo here runs from, is
  detached, clean and integrated, and after a quiet week R6 as written would have proposed it.
  This narrows R6. Owner confirmed 2026-10-22 ("Yes to both decisions").
- Chunk 01: offline, a remote-tracking ref whose remote branch is already gone looks like a
  merged remote branch (`origin/docs/goal-grounding` here). The online dry run fetches with
  `--prune` first (Chunk 03), so it drops out there. Offline it stays listed as unchecked.
- Chunk 03: `[DECISION: delete local branches with a re-proved compare-and-delete (git update-ref
  -d refs/heads/<b> <sha>) rather than R2's git branch -d | measured that -d checks merge into
  HEAD or upstream, not into the long-lived branch that is the proof, so it refuses this clone's
  worktree-agent branches (merged into main, HEAD on a develop-based branch) and the tool could
  never tidy them; R2's purpose, nothing unproven dropped, holds because the proof is re-run just
  before and the delete is conditional on the exact commit; no -D or --force anywhere | owner can
  veto]`. R2's clause is left as written, with the departure recorded beneath it. Not settled by
  the goals. Owner confirmed 2026-10-22 ("Yes to both decisions").
- Chunk 04: the session digest gets no sentence, a departure from this chunk's deliverable list.
  The digest's 500-character reserve is for a default no other surface carries, and the full
  suite went red when the sentence spent it. This default reaches every onboarded repo through
  the `tidy-available` advisory, which runs at each session start, and through `/prawduct:pr`'s
  step 7. The authoring rule "a new default must land in the digest" protects defaults that live
  only in a place-once template, and this one does not. Settled by the goals (lean, out of the
  developer's way).
- Chunk 03: git's own error messages already redact URL credentials, so the scrub test injects
  the leaky message at the runner. The first version of that test passed with the scrub removed.

**Level:** High. Requirements are owner-confirmed, the volatile facts (gh 2.86 source, harness
worktree lifecycle) were verified, and every mutation is a git primitive with its own refusal.
The one inference: `release/*` is long-lived and `hotfix/*` is not (requirements, Definitions).

## Status

- [x] Chunk 01: Classifier and offline dry run
- [x] Chunk 02: Session-start advisory and the preference rows
- [x] Chunk 03: Apply, network legs and egress
- [x] Chunk 04: After-merge, reap, and the prose surfaces
Context: All four chunks are built, reviewed and committed. The cumulative review
(rev-20261023T042213Z-e0941aa1) found 0 blocking. Its warnings are fixed in the commit that
follows their verify pass, and its notes were accepted on the record. The owner confirmed both mid-build
decisions on 2026-10-22. What remains is a PR through `/prawduct:pr` when the owner asks. This
clone's own leftovers are still untidied: they make a live demonstration of `git-tidy`, which is
the owner's to run.

## Verification Strategy

Each chunk runs `git-tidy` against real temporary repos the tests build: a bare "remote", a
clone, linked worktrees, and a fake `gh` on `PATH` that records its argv and serves canned JSON.
After Chunk 01, and again after Chunk 03, run the dry run against this clone and compare it with
the requirements' measured set. Chunk 03's `--apply` is exercised on a throwaway clone of this
repo, never on this clone itself, until the owner says so.

## Build Chunks

### Chunk 01: Classifier and offline dry run

- **Description:** The read-only slice through everything: classify every local branch, remote
  branch and worktree, and print the dry run, without network or mutation. This proves the proof
  rules before anything deletes.
- **Depends on:** none
- **Artifacts consumed:** requirements R1, R2, R8, R10; design decisions 1, 2 and 4 (dry-run half).
- **Deliverables:**
  - new `plugin/lib/git_hygiene.py`: long-lived set, classifier and plan.
  - `gitstate.held_branches`, which `stranded_work` now reads.
  - `prawduct-hook git-tidy [--offline] [--json]`, which prints actions, proofs and fingerprint.
    Network legs are reported `unchecked` until Chunk 03.
- **Tests:** real-repo fixtures. Each of these classifies correctly:
  - an integrated branch (develop and main);
  - an unintegrated pushed branch;
  - a local-only branch;
  - a held branch;
  - a branch with one commit past its merged tip;
  - a missing worktree entry;
  - a locked agent worktree;
  - a dirty worktree, and a clean integrated idle sibling;
  - long-lived names (`release/x`, the base, `origin/HEAD`'s target).

  Also: the fingerprint is stable under reordering and changes when a tip moves; a git failure
  gives exit 3 and never "nothing to tidy". Red-verify: replacing the ancestry proof with an age
  check fails a test.
- **Acceptance criteria:** on this clone the offline dry run lists the five merged local branches,
  the missing worktree entry, and eight merged remotes awaiting the network check (the seven
  `claude/*` plus a stale tracking ref a fetch would prune). It omits `prawduct-live`, a detached
  checkout, and
  `fix/skew-note-harness-hooks` (locked worktree, unintegrated) and every unmerged branch.
  `stranded_work` tests stay green.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Session-start advisory and the preference rows

- **Description:** Make the dry run's existence visible at session start, as one combined advisory
  with no network, and give the product its policy rows.
- **Depends on:** Chunk 01
- **Artifacts consumed:** R6, R9; design decisions 2 and 7.
- **Deliverables:**
  - new `plugin/lib/git_hygiene_probes.py`, registered in `probe_families`;
  - `Branch cleanup` and `Long-lived branches` rows in the project-preferences template;
  - the advisory's owner and recommended actions route to `git-tidy`.
- **Tests:**
  - The probe is silent on a tidy repo and under `Branch cleanup: off`; an unrecognised value
    reads as `propose`.
  - The id is stable for an unchanged set and new when a candidate is added.
  - It makes no network call: `gh` is absent from `PATH`, the remote URL fails on contact, and
    the probe still answers.
  - Advisory text carries no internal id.
  - A sibling worktree appears only when clean, integrated and idle 7 days or more.
  - Red-verify the off switch and the sibling idle floor.
- **Acceptance criteria:** a session start on this clone raises one `tidy-available` advisory whose
  evidence matches Chunk 01's dry run. `/prawduct:advisory` lists it, and dismissing it holds
  across a second sync.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Apply, network legs and egress

- **Description:** The keystone: deletion. `--apply <fingerprint>` runs the approved set with
  per-action re-proof. The network legs land here: `fetch --prune`, the open-PR check on remote
  candidates, and squash proof by compare-and-delete. They are declared as egress sites.
- **Depends on:** Chunk 02
- **Artifacts consumed:** R2, R3, R7, R8; design decisions 3, 4 and 8.
- **Deliverables:**
  - `--apply` with fingerprint refusal;
  - the network legs and the 8-branch squash-proof cap, with its overflow reported;
  - egress sites added to `security-model.md` and `project-state.yaml` `egress_boundary`.
- **Foreign API:** gh-cli
- **Critic mode:** chunk
- **Tests:**
  - A stale fingerprint changes nothing.
  - A branch that gains a commit between the dry run and `--apply` is kept, with the reason
    reported.
  - A removal whose proof no longer holds is kept, with the reason reported.
  - Compare-and-delete refuses when the ref moved.
  - A remote branch that is an open PR's base or head is skipped, using a fake `gh`.
  - A cross-repo head is never pushed to.
  - One failed action doesn't stop the others, and the exit code is 1.
  - `--offline` makes no `gh` or fetch call.
  - Red-verify the re-proof, the open-PR skip, and the CAS old-value.
- **Acceptance criteria:** on a throwaway clone of this repo, `git-tidy` then `--apply <fp>` removes
  exactly the dry run's set and nothing else (`git branch`, `git worktree list` and the remote
  refs compared before and after). A second dry run says nothing to tidy, with every leg checked.
- **Done when:**
  0. verify-api: run `gh pr list --state merged --head <b> --json number,headRefOid` and `gh pr
     list --base <b> --state open --json number,isCrossRepository` against this repo, and
     capture the real shapes in the test fakes' fixtures
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: After-merge, reap, and the prose surfaces

- **Description:** The two targeted moments, plus every surface that describes cleanup. The prose
  must agree with the mechanism (core learning: a mechanism change is done when everything
  describing it agrees).
- **Depends on:** Chunk 03
- **Artifacts consumed:** R4, R5; design decisions 5 and 6.
- **Deliverables:**
  - `git-tidy --after-merge <branch> [--pr <n>]` and `git-tidy --reap <worktree>`;
  - PR skill merge step 7 becomes the one call;
  - `delegation.md` reaping names `--reap`;
  - the session digest: descoped, with the reason under Decisions made mid-build;
  - the janitor theme routes to `git-tidy`;
  - a change fragment under `.prawduct/changes/`.
- **Foreign API:** gh-cli
- **Type:** cumulative-final
- **Tests:**
  - After-merge from a linked worktree whose base is held elsewhere ends detached at the updated
    base, with both the local and the remote branch gone.
  - From the main worktree it ends on the base, fast-forwarded.
  - A stacked PR is retargeted before the remote delete (fake `gh` argv order).
  - A long-lived head is kept.
  - `Branch cleanup: off` keeps the branches, except under a squash `PR merge strategy`.
  - Reap removes a clean integrated delegate worktree and its branch, and refuses dirty, locked
    or unintegrated ones.
  - A sweep for the prose claim "switch to base branch" and for gh `--delete-branch` finds no
    stale sentence.
- **Acceptance criteria:** all tests pass. The PR skill, delegation.md, digest and janitor theme
  describe the shipped behaviour, and the digest budget test is green.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
