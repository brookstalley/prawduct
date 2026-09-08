---
artifact: build-plan
version: 2
scope: upstream-intake-repoint
branch: feat/upstream-report-bug
depends_on:
  - artifact: backlog-service-upstream-filing
  - artifact: backlog-service-requirements
  - artifact: backlog-service-api-contract
governed_by:
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → **conforms, and Chunk 01 is where this norm stops being inapplicable to this program.** Wave B was outbound-only; the repointed probe is the first prawduct surface that reads foreign-authored issue rows and renders anything from them into the session briefing. It renders a COUNT and fixed prose — no title, body, author or label text from a filed issue reaches the advisory, the evidence tuple, or the briefing. The count-only shape is required by this norm first and by D14 (count-independent evidence ids) second; the two agree, and if they ever disagreed this norm wins"
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level → **applies, and the build declines the operation rather than seeking approval for it.** `incoming-bugs/` is gitignored, so its 34 archived reports have no git copy and `rm -rf` is unrecoverable. Chunk 02 retires the drop-box as a CHANNEL — the resolver, the pointer, the template, the prose — and never deletes an operator's local tree. The `.gitignore` line stays (re-commented as a retired local artifact) so a tree that still holds the directory stays quiet"
      - "a governed product's content leaves its owner only through a pinned, per-filing-approved surface → conforms; nothing here touches an egress path. The probe reads the local backlog cache and writes only into this clone's gitignored advisory store"
  - artifact: architecture
    dispositions:
      - "local-first: governance coordination is process-spawn + files + git, no network → **conforms, and it is the constraint that picks the data source.** The probe reads `lib/backlog/cachequery`, which is offline by construction, and never syncs. A probe that fetched to answer a nudge would put the network on the session-start path"
      - "authority fails closed; advice fails soft → conforms, and the learning this repo already paid for sharpens it: *advice fails soft is not advice fails silent*. In the receiving repo a cache that is unreadable or never synced yields ONE advisory naming the consequence (the intake count is unknown and reports may be sitting unread), never a raise and never silence. Outside the receiving repo the probe is inapplicable, which is a different state and reports nothing"
      - "every fact has one home → conforms, and it is what the probe imports rather than restates: `upstream.PINNED_TARGET` (who the receiver is), `upstream.TITLE_PREFIX` (the convention), `cachequery.unstaged_items` (what untriaged means). The intake query's definition stays at `documentation/backlog-service-upstream-filing.md` §6 and the probe cites it"
      - "goals and verification bind; prescribed method is advice → the `Deliverables` lists below are a guess made before the files were re-read; a builder who finds the passage lives somewhere else takes the better route and records it here"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms; Chunk 02 REMOVES a managed path (`.prawduct/.bug-inbox`) from the session-file registry rather than adding one"
      - "prawduct is Python and must never be specific to Python → conforms; no gate, canary or language dispatch is touched"
      - "prawduct guides and reviews; it never implements → conforms; this is prawduct's own governance surface"
      - "an independent reviewer never mutates the session it reviews → inapplicable; no chunk touches a reviewer write path or the Critic data plane"
  - artifact: data-model
    dispositions:
      - "`backlog_service_repo` selects which backlog store is authoritative → **conforms and is load-bearing twice.** It is one of the two signals `resolve_self_identity` reads to decide whether this repo IS the receiver, and it is the scope the cache read is keyed on. A repo with it unset resolves no identity, so the probe is inapplicable there rather than guessing"
      - "two stores, two lifetimes → conforms. The count is derived on read from the gitignored cache and lands in the gitignored advisory store; nothing new is committed, and no cache state reaches `project-state.yaml`"
      - "derived views are disposable and never authoritative → conforms; the count is recomputed every sync and no gate reads it"
      - "a governance document reaches a terminal state; it is never deleted → **inapplicable to what Chunk 02 deletes, and the distinction is worth stating.** `lib/bug_inbox.py` and `templates/incoming-bug-report.md` are code and a scaffold asset, not governance documents — code is deleted, not archived. The drop-box's REPORTS are covered by their own contract, which the retiring skill states: the backlog item, not the gitignored report, is the durable record, and every archived report already has one"
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules → inapplicable; no chunk writes an issue"
      - "facts are immutable and append-only → inapplicable; no fact is written"
      - "a fact written by a newer schema than the reader is a loud block → inapplicable; no schema changes. The probe reads the cache through `cachequery`, which owns that posture already"
      - "governance verdicts are computed from the fact ledger, never model-written state → inapplicable; no chunk touches the Critic data plane"
  - artifact: api-contract
    dispositions:
      - "additive-first evolution; deprecation is signalled, never silent → **applies, and it is why `bug-inbox` is not deleted in Chunk 02.** The 2026-08-11 exception covers subcommands *the harness alone invokes*; `bug-inbox` is human/skill-callable and has no `hooks.json` registration to drop, so the exception does not reach it and the ruling [[deprecation-requires-an-inert-retention-window]] governs. It becomes inert — `return 0`, a docstring, a `notice:` on stderr — joining the `regen-views`/`stamp-merged` tier that warns because a person can act on the warning. The dispatch branch is deleted in a later release, not here"
      - "exit codes are the contract; message severity is a stable prefix vocabulary → conforms; the inert `bug-inbox` moves from `1` (no inbox resolved) to `0` (retired), which is the shape the retained tier already uses, and the `notice:` prefix is the existing vocabulary"
      - "whole-surface semantic versioning; the internal CLI subcommand surface carries no per-subcommand version → conforms; `bug-inbox` is in neither stable-tier subcommand"
partition: serial — 02 retires exactly what 01's replacement makes retirable, and that ordering IS design §7's lockstep. The two also collide on `plugin/skills/report-bug/SKILL.md`'s receiving-side section, which 01 makes stale and 02 rewrites
last_validated: 2026-09-08
---

## Requirements Confidence

**Level:** High

**Why:** design §6 and §7.4 pin both halves, the owner approved them, and Wave A/B built everything
this stands on. The one thing the design deliberately left to build — *"exact intake query + advisory
repoint, pinned on the receiving-side item, not here"* — is settled by what the codebase already
owns: `upstream.PINNED_TARGET` says who the receiver is, `upstream.TITLE_PREFIX` says what the
convention is, and `cachequery.unstaged_items` already implements *open and carrying no stage*, which
is this repo's triage label. Nothing is being derived; three constants are being composed.

**Open assumptions / unknowns:**

`[ASSUMPTION: "no triage label" means "no stage: label" | MED impact | user can correct]` — design §6
says *no triage label* without naming which. This repo's triage ladder is `stage:`, and
`cachequery.unstaged_items` already treats its absence as never-triaged (and NULL and empty string
alike, deliberately). `area:`/`impact:`/`kind:` are classification, not triage state. If the owner
means any-label-at-all, the query narrows and the probe under-reports; correcting it is a one-line
predicate change.

`[ASSUMPTION: the probe applies only where this repo IS the pinned upstream target | LOW impact | user
can override]` — the outgoing probe was inert *by absence* (no product repo has `incoming-bugs/`).
The intake set has no such natural absence: a product repo's cache is present, readable, and simply
holds nothing `[prawduct]`-prefixed, which would make every product's degraded-cache path speak about
a channel it does not receive on. Keying applicability on `PINNED_TARGET in resolve_self_identity()`
restores inert-by-identity and lets the receiving repo report a broken cache honestly. Both halves of
that trade are the reason it is written down.

`[ASSUMPTION: VRF-018 confirms a non-collaborator cannot apply a label | MED impact | user can veto]` —
**unchanged and still owner-blocked.** The build ships to the recalled answer, exactly as Wave B
shipped the label-less payload to it. If the answer comes back the other way, a filer can self-apply
`stage:ready` and drop out of the intake count, and §6's query needs **re-deriving rather than
re-confirming**. It gates the release, not this plan.

**What would raise confidence:** N/A at High. VRF-018 is the one genuinely open question and it is
scheduled as a release gate rather than assumed away.

## Status

- [x] Chunk 01: `untriaged-upstream-reports` counts the intake set instead of the drop-box
- [x] Chunk 02: the drop-box retires, and every surface still describing it stops

**Chunk 01 complete, 2026-09-08.** The advisory counts the intake set; three constants compose the
query and the probe spells none of them. Three review rounds, and the same test failed the first two:
a no-network pin has to guard the **seam an absence would cross** and assert something **only the
path under test can produce**. Round one did neither (a counter on a fake the probe never receives);
round two guarded a seam that turned out to be the global `subprocess.Popen`, which broke the `git`
call the probe legitimately makes and let the *degraded* branch satisfy a candidate count. What
Chunk 02 should carry forward from that: when a reviewer's finding is about a test that cannot fail,
the fix is not a better assertion, it is naming the seam.

Two review premises were checked rather than deferred to, and one was wrong: the scope-spelling
observation described a canonicalized lookup as reading "a scope with no rows", but `item` carries no
scope column, so the count is identical and nothing downstream goes red. The fix stands on
convention (`briefing.py` reads the raw scalar as scope; the cursor is keyed as declared) and its
test says out loud that it is a contract test with no behaviour to assert yet.

The commit's tree differs from the verified tree by the Status tick, this block, and two
**note-level** test edits the final round demoted — a second `pytest.raises` so the docstring's
"both interceptions are proved to bite" is true rather than half-true, and `monkeypatch.setattr` in
place of a hand-rolled `try/finally`. Named here rather than left implicit: Chunk 02's `cumulative`
spans `merge-base...HEAD` and is what covers them.

**Chunk 02 complete, 2026-09-08.** The retirement landed as designed on every substrate. Four things the build decided that
this list did not, recorded here because the cumulative grades against it:

1. **The inert notice is `WARNING:`, not `notice:`.** The `governed_by` disposition above claims
   `notice:` is "the existing vocabulary"; it is not — the api-contract's declared vocabulary is
   `CRITICAL:`/`WARNING:`/`NOTE:`/`PRAWDUCT:`/`BLOCKED —`, and the tier this joins (`regen-views`,
   `stamp-merged`) prints `WARNING:`. Taking the plan's literal prefix would have invented a fifth
   spelling for a command whose whole point is joining an existing tier.
2. **The inert contract is pinned in `tests/test_deprecated_inert_commands.py`, not
   `test_retired_hook_subcommands.py`.** The latter is scoped to commands a shipped `hooks.json`
   registers and to the *silent* tier; the former is the *announcing* tier and already held
   `regen-views`/`stamp-merged`. `bug-inbox` is human-callable, so it belongs with them —
   `test_retired_hook_subcommands.py` gains only the cross-tier `_EPHEMERAL_SAFE_COMMANDS` pin,
   which is the one claim that spans both.
3. **The grep-shaped pin is two rules of different shapes**, in `tests/test_drop_box_retirement.py`.
   A single token ban could not hold: write-path machinery (the env knob, resolver, pointer,
   write-target template, report scaffold, archive destination) is illegal *everywhere* in the
   shipped tree, while the directory NAME is legal in code that announces the retirement and illegal
   in anything a model reads as instruction. Both legs carry a positive control, because every
   assertion in them is an emptiness check.
4. **Three worked examples were repointed, and they were not on the list.** `buildplan_refs`' and
   `gitstate`'s gitignored-managed-path and angle-bracket-write-target examples named the retired
   pointer and `<inbox>/`; `briefing.py`'s prerequisite-ordering docstring described the
   drop-box→migration edge in the present tense. Same rule Chunk 01 paid for: a claim's home and its
   truth-condition are different things, and these went false when the substrate did.

5. **`#194` and `#234` do not close here, and step 3 above is corrected rather than followed.**
   It was written against the markdown convention, where the archive is a file edit that rides in
   the PR and is atomic with the merge. This repo is on the Issues backend, where a close is an
   immediate API side effect — the exact drift `#697` shipped to stop. `#217`'s taxonomy note is
   posted (a comment is additive and safe on a branch); the two closes are handed to the merge.
   Worth naming in the closing note: `#234`'s stated acceptance ("the advisory counts *labeled*
   issues") was superseded by §6's title-prefix query, so a reader diffing acceptance against the
   code will trip on it. The item is done by the retirement; its checkbox is not what was built.

`incoming-bugs/` itself is untouched, its `.gitignore` line re-commented beside the retired
`.prawduct/.bug-inbox` pointer. `#234` closes on the retirement half; its `adopt` leg — the owner's
2026-08-03 ruling that a loud arrival still needs a route out — is `#542`, open and `stage: ready`,
so it is handed on rather than closed with the item.

**The `cumulative` (`rev-20260908T220843Z-9c210bc4`, `40b772b2...b23a0ef6`) returned 0 blocking, and
its sharpest warning was about Chunk 01's code.** `unstaged_items` answers `ok` for a store whose last
sync FAILED, so *readable* and *current* are different questions and the probe asked only the first —
a stalled feed with rows printed a bare count as current, and with none went silent, which is the
false all-clear the chunk's own change-log paragraph claims to have avoided. Fixed, tested, and
mutation-checked in both branches. **The one thing Chunk 03 of anything should carry forward:** the
warning was not that a case was unhandled but that a *predicate was the wrong question*, and the
tell was available in the code — the in-code comment reasoned about the failing-sync case for the
counting branch only, and stopped one branch short.

Two departures inside that fix, both deliberate. The reviewer proposed carrying `sync_error` into the
copy; that string is a provider message relayed through `gh`, and advisory text is rendered into the
model's context at session start, so the advisory says a sync is failing and never what the provider
said. And hoisting the shared copy into module constants tripped `test_advisory_actionability.py`,
which reads advisory text statically at each construction site — the evasion it exists to prevent.
Copy is inlined and waived; the evidence string stays shared, because that is what makes the two
stalled shapes one thing to dismiss.

Six other findings, all fixed: the sweep's instruction class derived by exclusion rather than
enumerated (R-1), the injected-footprint ceiling ratcheted with its cut **and the
ceiling-is-reading-plus-one invariant now asserted** (R-3/R-5), the cross-cutting-concerns row's
fourth consumer named and its gap restated as observed (R-6), and two stale counts made relational
(R-2/R-7). R-4 and R-9 accepted with reasons — both are notes the reviewer marked no-action.

**One thing left standing, flagged rather than fixed:** record-lint names whichever
`.prawduct/learnings.md` rules currently exceed the 400-character ceiling. Dozens do — run the lint
for the live set rather than trusting a figure written here, which is the shape this chunk kept
tripping over. The standing session advisory asks for the whole file to be compacted into
`learnings-detail.md`, and trimming whichever entries the lint happens to name is motion, not that
job. It gates nothing. (The two rules this chunk added went in compact, and the corollary it hung on
the ratcheting rule had its narrative moved to the detail file for the same reason.)

Context: Wave C of the BKL-7Q4M program (A = the adapter, shipped at `40b772b2`; B =
`build-plan-upstream-report-bug.md`, complete and unmerged on this branch; C = this). The owner ruled
2026-09-06 that **the release cuts after all three waves**, so this plan does not close the release
either — but its commit does close `#194` (BKL-7Q4M) and `#234`, and settles the taxonomy half of
`#217`.

**Two plans claim `feat/upstream-report-bug` and that is the documented ordinary case.** Wave B's
plan has every box ticked and stays live until its commits reach `origin/develop`; this one holds
open chunks, so the branch-claim precedence resolves *this* plan and the session briefing says which.
Nothing needs repointing, and `active_build_plan` stays `null`.

**One accepted observation from Wave B is owed to the next commit touching
`tests/preferences/test_no_upstream_content_egress.py`.** Chunk 02 discharges it deliberately rather
than waiting for a commit that file happens to get: the docstring summary and assertion message of
`test_no_command_block_passes_a_composed_field_as_a_shell_literal` still enumerate
"`--title`/`--component`" after `--body` joined the class. **The fix is deleting the enumeration from
both, not extending it.**

## Scaffolding

Not applicable — an existing, scaffolded project. `pytest tests/ -q` is the suite;
`python3 plugin/bin/prawduct-hook` is the CLI under test.

### Verification Strategy

Beyond the suite, two things, because both chunks ship text a human reads at session start and a
green test proves the text exists rather than that it lands.

- **Chunk 01** — run the real session-start path in this checkout (`prawduct-hook clear`) and read
  the advisory block as the owner will. It should name a count and a consequence in plain language
  and carry no issue title, no author, and no internal probe identifier. Then break the cache
  (rename it) and run it again: the degraded line must name what is now unknown rather than
  disappearing. Restore the cache afterwards.
- **Chunk 02** — walk `/prawduct:report-bug`'s receiving-side section as a model in the prawduct repo
  would, and confirm it routes to the issue intake set with no step that reaches for a directory.
  Then run `prawduct-hook bug-inbox` and confirm it exits 0 with a `notice:` on stderr and nothing on
  stdout.

## Build Chunks

### Chunk 01: `untriaged-upstream-reports` counts the intake set instead of the drop-box

- **Description:** The advisory stops counting files in a gitignored directory nothing writes to and
  starts counting the channel that actually grows — open issues on prawduct's own tracker carrying
  the `[prawduct]` title convention and no triage label (design §6). This is the load-bearing half of
  Wave C: until it lands, issue-side triage is manual and the skill says so, and a framework session
  that drains only the drop-box drains the dead channel. It is also the first prawduct surface to
  read foreign-authored rows, which is why the security disposition above stops being inapplicable
  here.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-service-upstream-filing.md` §6 (the intake query and
  why it works for both the non-collaborator and dogfood cases), §7.4 (the repoint as one act with
  the retirement); `documentation/post-sync-advisory-spec.md` (probe contract, `probe_version`
  supersession, `prerequisite_of`)
- **Deliverables:**
  - `plugin/lib/upstream_probes.py` — rewritten. `PROBE_VERSION` → `2`, which supersedes any live
    drop-box advisory cleanly rather than leaving a stale one behind. Applicability:
    `upstream.PINNED_TARGET in upstream.resolve_self_identity(codebase.root)`; anything else returns
    `[]`. Count: `cachequery.unstaged_items(...)` scoped by `backlog_service_repo`, filtered to
    titles starting with `upstream.TITLE_PREFIX`. **Nothing from a row's text is carried into the
    candidate** — the evidence tuple stays qualitative and count-independent, and the summary carries
    the count and nothing else.
  - The same file's degraded path — when the probe applies and the cache read comes back
    `unavailable`, one candidate saying the intake count is unknown and reports may be sitting
    unread. Advice fails soft, not silent.
  - The same file's `prerequisite_of` — **removed**, with the reason in a comment. It ordered
    incoming-bug triage ahead of the backlog migration; the migration shipped, prawduct is
    post-cutover, and an ordering constraint whose second term can no longer fire is a dead edge.
    This falsifies the worked example at `documentation/post-sync-advisory-spec.md` (~`:259`–`:317`),
    which is Chunk 02's coherence work and is named there.
  - `plugin/skills/report-bug/SKILL.md` — the receiving-side paragraph that says *"Issue-side triage
    is manual until the advisory is repointed"* and *"Nothing counts the issues yet"*. Both become
    false in this chunk. The drop-box paragraph below them is Chunk 02's.
  - `.prawduct/operator-verification.md` — a `Visual change` entry for the new advisory prose.
- **Tests:** `tests/test_upstream_probes.py`, rewritten against a real cache fixture rather than a
  stubbed query — this repo has already been burned by a self-referential probe test that passed
  because the gitignored cache was unreachable in CI and the assertion never reached its subject, so
  **every case here asserts the subject was reached** (the probe read a cache and returned a decision
  about it), not merely that nothing fired. Cases: a receiving repo with N prefixed unstaged issues
  fires with count N; a prefixed issue carrying a `stage:` is not counted; an unprefixed unstaged
  issue is not counted (this repo's own untriaged backlog items must not leak into the intake nudge);
  a non-receiving repo is inapplicable and silent; a receiving repo whose cache is unreadable fires
  the degraded candidate and names the consequence; and a negative pin that **no filed-issue text
  appears anywhere in the emitted candidate** — seed a row whose title carries a distinctive marker
  and assert it appears in no field.
- **Acceptance criteria:** `pytest tests/ -q` green. In this checkout, `prawduct-hook clear` produces
  an advisory whose count matches the issue set a maintainer would get by hand. The probe makes no
  network call — pin it, since the cache API is offline by construction but a future edit need not
  be.
- **Critic mode:** chunk
- **Visual change:** yes
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=upstream-intake-repoint`, no `release=`)
  3. `.prawduct/operator-verification.md` entry appended for the new advisory prose
  4. `/prawduct:critic` run and blocking findings resolved
  5. Committed and chunk marked `[x]` in Status

### Chunk 02: the drop-box retires, and every surface still describing it stops

- **Description:** With the replacement counting, design §7.4's other half. The retirement is one act
  **per substrate** the drop-box lives on — a module, a CLI subcommand, a session-file registry
  entry, a scaffold template, a `.gitignore` line, and six prose surfaces — and the substrates do not
  all take the same treatment: the module is deleted, the subcommand is retained inert, and the
  operator's local directory is not touched at all.
- **Depends on:** Chunk 01 — the drop-box is retired only once something else counts the channel.
  Reversing the order is the one sequencing design §7 forbids, and `#234` is the guard that says so.
- **Artifacts consumed:** `documentation/backlog-service-upstream-filing.md` §7.4; `.prawduct/artifacts/api-contract.md`
  § Direction (the deprecation ruling that decides the subcommand's treatment)
- **Deliverables:**
  - `plugin/lib/bug_inbox.py` deleted — caller-less internal module, no CLI surface of its own.
  - `plugin/bin/prawduct-hook` `cmd_bug_inbox` — **inert, not deleted.** `return 0`, a docstring
    saying what it was and when it goes, a `notice:` on stderr naming the retirement. It joins the
    warning tier (`regen-views`, `stamp-merged`), not the silent one: those two are silent because
    their caller is a stale registration that cannot read a warning, and this one's caller is a
    person who can.
  - `tests/test_retired_hook_subcommands.py` — `bug-inbox` recorded in the retired tier, so the
    inert-retention contract is pinned rather than remembered.
  - `.prawduct/.bug-inbox` — removed from the session-file registry (`plugin/lib/core.py:79` and the
    `.gitignore` contract), and from the docstring examples that name it as the illustrative managed
    path (`plugin/lib/gitstate.py:716`, `plugin/lib/buildplan_refs.py:2690`) — those need a live
    example, not a retired one.
  - `.gitignore` — the `incoming-bugs/` line **stays**, re-commented as a retired local artifact.
    Removing it would surface an operator's untracked archive as git noise, and deleting the tree is
    an unrecoverable operation this plan declines (see the security disposition).
  - `plugin/templates/incoming-bug-report.md` deleted — a scaffold for a report shape nothing
    produces.
  - `plugin/skills/report-bug/SKILL.md` — the drop-box triage steps (~`:303`–`:315`) go; the
    receiving-side section is the issue intake set alone.
  - `documentation/project-structure.md` (~`:51`) and `plugin/skills/backlog/migration-scrub.md`
    (~`:559`, the lockstep clause that has now fired).
  - **Not here any more, done in Chunk 01:** the `CLAUDE.md` product-feedback row and
    `documentation/post-sync-advisory-spec.md`'s `prerequisite_of` example (§5 and §5.3). Both went
    false when the probe was repointed rather than when the drop-box retires, so they were corrected
    in the chunk that falsified them. Struck from this list rather than left standing, because the
    cumulative review grades against it.
  - `tests/preferences/test_no_upstream_content_egress.py` — Wave B's owed observation: delete the
    stale `--title`/`--component` enumeration from the docstring summary and the assertion message of
    `test_no_command_block_passes_a_composed_field_as_a_shell_literal`.
  - `documentation/backlog-service-requirements.md` (~`:182`) — deferred out of Chunk 01 and named
    here so it cannot drop. It lists the `untriaged-upstream-reports` probe among the things "**to be
    removed**", and calls the drop-box "the interim supported path until the GitHub-issue path is
    built". Both clauses have expired: the path is built, and the design chose to **repoint** the
    probe rather than remove it. Record the divergence the way §8 of the design records its others —
    the requirement is the history of what was asked for, corrected in place with a dated note, never
    rewritten to agree with the code.
  - `documentation/backlog-service-upstream-filing.md` §7 — mark step 4 done, once it is. §6 was
    settled in Chunk 01 and already carries the query it landed on.
  - `#194`, `#234` closed and `#217`'s taxonomy half settled, via `/prawduct:backlog`.
- **Tests:** the suite's existing pins carry most of this — `test_hook_argument_shape.py`,
  `test_hook_session_file_registry.py`, `test_gitignore_probes.py`, `test_plugin_packaging.py` and
  `test_plugin_runtime.py` all name one of these paths today and must be brought to the new truth
  rather than around it. New: the inert-`bug-inbox` contract in `test_retired_hook_subcommands.py`,
  and a grep-shaped pin that no shipped skill, template or doc names the drop-box as a live
  destination — *removing a mechanism requires removing its name too*, and a grep is the only thing
  that quantifies over the surfaces rather than the ones I remembered.
- **Acceptance criteria:** `pytest tests/ -q` green. `prawduct-hook bug-inbox` exits 0, prints
  nothing on stdout, and prints one `notice:` line on stderr. No live skill, template, doc or
  `CLAUDE.md` line describes the drop-box as somewhere a report goes. `prawduct-hook clear` in a
  freshly-scaffolded throwaway product is unchanged and silent about upstream intake.
- **Critic mode:** cumulative
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=upstream-intake-repoint`, no `release=`)
  3. `#217` updated via `/prawduct:backlog` — on the branch, because a comment is additive.
     `#194` and `#234` close **at the merge**, through `/prawduct:pr`'s Merge Flow, NOT here: on the
     Issues backend `status --to shipped` closes over the API the moment it runs, with no branch to
     be abandoned with, so a branch-time close leaves them wrongly closed if this PR is reworked
     (#697, which records #687 and #688 as instances). `#234` closes as `upstream-intake-repoint`
     and `#194` as `feat/upstream-report-bug` — the program spans three waves and no single scope
     name is the honest handle for it
  4. Committed, then `/prawduct:critic cumulative` run once over `merge-base...HEAD` (it covers Wave
     B and Wave C together, which is what this branch ships as one PR) and blocking findings resolved
  5. Chunk marked `[x]` in Status
