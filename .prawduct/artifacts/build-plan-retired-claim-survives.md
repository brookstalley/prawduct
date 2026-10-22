---
artifact: build-plan
version: 2
scope: retired-claim-survives
branch: feature/retired-claim-survives
depends_on:
  - artifact: nonfunctional-requirements
governed_by:
  # Seeded with `prawduct-hook jurisdiction --artifacts-only` over a one-paragraph
  # description of #136, then curated to the artifacts carrying a `## Direction`
  # that binds a record-lint check (the ranker's release/audit hits carry none).
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost x run-count -> conforms. The check runs at
        `critic-begin` in code; it adds manifest lines only when it fires, and a surviving retired
        claim caught here is a round the Critic's Goal 4 read no longer has to buy."
      - "proportionality ratchets both ways; a new control names its yield and emits it -> conforms.
        Expected yield: literal survivors of a declared retirement, in tracked files and open
        issues (cause classes 1, 3, 5 of #136). Emission: its per-check count rides the dispatch
        manifest into the review fact like every record-lint check, so its firing rate is an
        evidence-store query."
      - "state-file growth is advisory, never a hard block -> inapplicable because this plan adds
        no state file and grows none."
      - "review rigor is stage-keyed -> conforms. Severity is WARNING, so at the inner stage it is
        an observation and only the boundary review raises it; it never enters the inner BLOCKING
        set. This norm's own `Retires:` line becomes the first live declaration the check reads."
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews -> inapplicable because the
        check is read-only and runs before reviewers are dispatched."
      - "authority fails closed; advice fails soft -> conforms. Advice: it never gates. A leg that
        cannot read its input reports `unchecked` with a reason, never an empty pass."
      - "local-first: process-spawn + files + git object DB, no network, no third-party deps ->
        conforms. `git grep` over the worktree plus the local backlog cache; never the provider."
      - "the plugin writes nothing into a governed repo except its own state -> conforms; writes
        nothing at all."
      - "Python-implemented, never Python-specific -> conforms. Text match over any tracked file;
        the waiver is the comment-leader-agnostic `prawduct:allow` pragma."
      - "prawduct guides and reviews; it never implements -> inapplicable because the check reads
        governance prose and reports; it writes no product code."
      - "goals and verification bind; prescribed method is advice -> conforms, and used: #136
        prescribes `git grep -n -F` per phrase. This plan keeps its goals (catch classes 1/3/5) and
        departs from the method where the method cannot meet them — see Goals, Decisions."
      - "every fact has one home -> conforms. The `Retires:` convention's home is `docs/norms.md`
        § Anatomy; severity's home is `cross-checks.md` Record-Lint; the coverage statement's home
        is the check's docstring. Every other surface references one of those."
  - artifact: data-model
    dispositions:
      - "verdicts come from the fact ledger, never mutable model-written state -> inapplicable
        because record-lint is advice and decides no verdict."
      - "facts are immutable and append-only -> inapplicable because the check writes no fact; its
        counts ride the existing consolidation path."
      - "derived views are never authoritative; no gate reads a view -> conforms. The backlog leg
        reads the local cache (a derived view) for advice only; no gate consumes the result."
      - "a governance document reaches a terminal state, never deleted; a live document outranks
        an archived namesake -> conforms. Archived documents are history and are not searched."
      - "every backlog write conforms to the issue title rules -> inapplicable because the check
        writes no issue."
      - "a fact from a newer schema is a loud block -> inapplicable because no fact is read."
      - "two stores, two lifetimes -> conforms. Declarations live in committed records; the check
        keeps no state."
      - "`backlog_service_repo` selects the authoritative backlog; once set, `backlog.md` is
        frozen history -> conforms, and it shapes the design. Set: the backlog leg reads the cache
        through `cachequery`, and `.prawduct/backlog.md` is excluded from the file leg as history.
        Unset: `backlog.md` is the live backlog and an ordinary tracked file, so the file leg
        covers class 5 and no separate leg runs."
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; the evidence store independently schema-versioned -> conforms. One
        new `counts` key in `record_lint`, carried by the existing path; no schema change."
      - "exit codes are the contract -> inapplicable because no CLI surface or exit code changes."
      - "additive-first; `--json` readers tolerate unknown keys -> conforms. A new check name is an
        added key in `counts`; nothing is repurposed."
partition: serial, because Chunk 02's dogfood sweep and replay fixtures run Chunk 01's check
---

# Build Plan — retired-claim-survives (#136)

## Goals

**Response taken:** Proceed, citing it — #136 is `stage: ready` with a decided design, an
acceptance list and a scope-out. The owner said "let's get 136" on 2026-10-22.

**Product:** When a governing record retires a claim, its old wording keeps surviving in places
the author's sweep never reached. In one governed product that happened thirteen times in four
sessions, and the author's own check caught none of them. A learning broken again after its own
remedy needs a structural check, not a stronger reminder. This adds that check for the literal
cases.

**What it is:** a `retired-claim-survives` record-lint check. Its input is a `Retires:` field
listing retired phrasings as double-quoted strings. The field sits on a `## Direction` norm entry
in `.prawduct/artifacts/*.md`, or is a `retires:` list on a `technical_decisions` /
`design_decisions` entry in `.prawduct/project-state.yaml`. Every surviving phrase in a tracked
file or an open backlog issue is a WARNING finding at `file:line` naming the declaring record.

**Coverage, stated honestly** (the docstring carries this): catches cause classes 1 (literal
survival), 3 (the survivor sits in a file the author is editing) and 5 (the survivor sits in the
backlog). It does not catch class 2 (paraphrase): Critic Goal 4 owns that, and an author can list
known paraphrases as extra phrases. It does not catch class 4 (a finding's enumerated sites half
consumed): `verify-resolutions` owns that.

**Constraints:** advice only, with no new gate or hook (#136). Never silently pass: an unreadable
input is `unchecked`. No YAML dependency, matching record-lint.

**Inferences** (mine, for the boundary review to show the owner):
- *Acknowledgement is a waiver.* A site that quotes a retired claim as its subject, such as an
  absence test or an analysis arguing against it, is not a survivor. Without a way to say so, the
  check fires on that site forever and gets ignored. #136's title says "acknowledge" but its body
  names no mechanism, so I reuse the repo's existing one: `prawduct:allow
  prawduct/retired-claim-survives -- <why the quote is the point>`, on the line or the line above.
  `chunk-ref-missing` is the precedent. The same pragma is honoured inside an issue body.
- *Matching is case-insensitive and tolerates line wraps.* #136 prescribes `git grep -n -F` per
  phrase. This repo hard-wraps prose at about 100 columns, so a multi-word phrase often straddles
  a newline, and `-F` misses exactly that survivor. A capitalised sentence start would be missed
  too. Instead, `git grep -l` narrows the files by each phrase's longest word, then a regex runs
  over the file text with words joined by whitespace. The whitespace may carry a line-leading
  comment or quote marker (`#`, `//`, `>`, `*`). The goal binds and the method is advice, per the
  architecture norm above.
- *A `Retires:` field is never itself a survivor,* wherever it sits. Another record that also
  declares the phrase is a declaration, not an assertion.
- *History is excluded:* `/archive/` paths, `.prawduct/changes/`, change-log files
  (`change-log*`, `CHANGELOG*`, `change-log-archive/`), and `.prawduct/backlog.md` once
  `backlog_service_repo` is set (data-model norm). Files the current diff edits are **not**
  excluded (class 3).
- *Repo-wide, not diff-scoped.* Record-lint's line checks read only added lines. This check
  cannot: its whole target is text the diff did not touch. The cost is bounded by one `git grep -l`
  plus reading the candidate files. `architecture.md` and the module docstring state the
  exception.
- *Line-start `Retires:` only.* A `Retires:` written inline after a bullet's bold statement is not
  read. `norm_probes` owns inline splitting, and widening it changes what every norm probe reads.
  `norms.md` documents the line-start form.

**Tradeoffs accepted:** the backlog leg reads every open item's body in-process
(`cachequery.open_items`) instead of calling `cache-query search` per phrase. FTS search matches
terms, not phrases, so its hits would need the same exact filter anyway, and one scan of about 170
rows answers every phrase at once.

**Decisions made mid-build:**
- Chunk 01 — the severity rows (`cross-checks.md`, `goals-1-3.md`, `cross-cutting-concerns.md`) and the `waivers.md` registry row moved here from Chunk 02: a registry guard requires every check's severity on the reviewer surfaces, and `waivers.md` requires the row in the change that honours the id. Settled by the repo's own guards.

**Level:** High — the design is settled on the issue, the code it extends was read on develop
2026-10-22, and nothing here depends on fast-moving external facts.

## Status

- [x] Chunk 01: The check — `Retires:` declarations read, tracked files and open issues searched
- [ ] Chunk 02: The convention, the dogfood sweep, and the replay
Context: Plan written 2026-10-22 on `feature/retired-claim-survives`, cut from develop @ 7d8c24a2.
#136 is `in-progress`; its `working_branch` claim needs the branch pushed first. Chunk 01 built
and committed; all twelve behaviour mutants killed, a wording control survived. Next: Chunk 02.
The first dogfood run over this repo found ten survivors of the stage-keyed norm's `Retires:`
line, two of them wrapped copies a plain `git grep -F` misses; Chunk 02 dispositions each.

## Build Chunks

### Chunk 01: The check — `Retires:` declarations read, tracked files and open issues searched

- **Description:** The mechanism. A new lib module reads declarations and searches for survivors.
  `record_lint` runs it on every dispatch, like the learnings checks that are not record-scoped,
  and reports findings, `unchecked` reasons and a count.
- **Depends on:** none
- **Artifacts consumed:** #136 (Proposed change, Acceptance), `plugin/docs/norms.md` § Anatomy,
  `plugin/docs/waivers.md`, `plugin/lib/norm_probes.py` (Direction section reading)
- **Deliverables:** new `plugin/lib/retired_claims.py`; `retired-claim-survives` in
  `record_lint.CHECKS`, wired into `lint_records`; new `tests/test_retired_claims.py`
- **Tests:** red first, written against the acceptance list. Fixture repo with a norm `Retires:`
  and the phrase in `docs/x.md` → a finding at that line. A wrapped and capitalised occurrence is
  caught. A file the diff edits is still reported. The declaring line, archive, change-log and
  fragment history are not. A waived line is not. A `technical_decisions` `retires:` list (flow
  and block forms) reads the same as a norm's. Backlog leg: an open issue carrying the phrase is
  reported, a closed one is not, a waived one is not. An unreadable cache gives `unchecked` and a
  `None` count, never a clean result. `backlog_service_repo` unset → no backlog leg and
  `backlog.md` searched; set → `backlog.md` excluded.
- **Acceptance criteria:** every #136 acceptance box except the replay and `norms.md` holds as a
  passing test; the check's docstring carries the class coverage statement.
- **Done when:**
  1. Acceptance criteria met and the chunk's tests pass (the record-lint and retired-claims files)
  2. Committed and chunk marked `[x]` in Status (a short plan's earlier chunk ticks at commit)

### Chunk 02: The convention, the dogfood sweep, and the replay

- **Description:** Make the convention the documented way to retire wording, and run the check on
  this repo. The stage-keyed norm's existing `Retires:` line becomes a live declaration, so every
  survivor it finds is fixed or waived with a reason. Replay the recorded recurrences as fixtures.
- **Depends on:** Chunk 01
- **Artifacts consumed:** the evidence product's recurrence record (#136 Evidence; restated, not
  copied)
- **Deliverables:** `norms.md` § Anatomy gains the `Retires` field and § Amendment the sentence;
  `waivers.md` registry row; `cross-checks.md` Record-Lint severity row and the `goals-1-3.md`
  WARNING list; `architecture.md` and the record-lint docstring state the repo-wide exception;
  `cachequery.open_items` names its new consumer; the dogfood sweep, so this repo's own run is
  clean or every hit is waived; replay fixtures in `tests/test_retired_claims.py`; a change-log
  fragment
- **Tests:** replay — each class-1/3/5 recurrence rebuilt as a fixture shape and caught; the
  class-2/4 ones asserted *not* caught, so the coverage statement is pinned both ways; the
  repo-level dogfood run clean.
- **Acceptance criteria:** the remaining #136 boxes; `record_lint` over this repo reports no
  unwaived `retired-claim-survives` finding in tracked files; the declared suite green.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the declared suite passes (recorded)
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
