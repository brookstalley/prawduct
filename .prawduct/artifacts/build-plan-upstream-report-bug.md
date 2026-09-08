---
artifact: build-plan
version: 2
scope: upstream-report-bug
branch: feat/upstream-report-bug
depends_on:
  - artifact: backlog-service-upstream-filing
  - artifact: backlog-service-requirements
  - artifact: backlog-service-api-contract
governed_by:
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → inapplicable because Wave B is still outbound-only; the intake half (reading foreign-authored issue bodies) is Wave C's `untriaged-upstream-reports` repoint, and no chunk here reads an issue it did not just write"
      - "a destructive or irreversible operation requires explicit owner approval at the OPERATION level → conforms, and Chunk 02 is where the norm stops being a property of the adapter and becomes a property of the flow a person actually runs. The operation is ONE filing; the approval is the L2 verbatim review of the exact bytes; the token is `--approve <digest>`. Chunk 02 grants `file-upstream` NO `allowed-tools` entry, so the permission prompt stands as a second, harness-level confirmation on both arms"
      - "a governed product's content leaves its owner only through a pinned, per-filing-approved surface → conforms; Wave A built the surface and Wave B routes the one caller onto it. Nothing here widens the target, the payload, or the check set"
  - artifact: architecture
    dispositions:
      - "local-first: two network surfaces are admitted, both off unless a person acts → conforms, and Wave B is the work that makes the second one's `off unless a person acts` true in practice rather than by absence of a caller. **The owner ratified the 2026-09-07 clarification on 2026-09-07 (this session); the `[DECISION: …]` is no longer vetoable-pending.** Chunk 01 records that ratification. No third surface is added: `report-bug` reaches the same pinned target through the same op"
      - "authority fails closed; advice fails soft → conforms, and Chunk 01 is a fails-closed decision in miniature. The `Upstream filing` row now EXISTS, so `read_filing_preference`'s absent-file branch stops being the only reachable path — an operator who writes a typo lands on `ask-user` with a warning, never on `always-file`"
      - "every fact has one home → conforms, and it is the constraint that shapes Chunk 02. The rewritten skill does not restate the refusal set, the digest recipe, or the payload shape: it cites `documentation/backlog-service-upstream-filing.md` §5 and §2, exactly as `adapter-mode.md` already does. A skill that copied the six refusals would be the seventh place they live"
      - "goals and verification bind; prescribed method is advice → the `Deliverables` lists below are a guess made before the files were re-read; a builder who finds the passage lives somewhere else takes the better route and records it here"
      - "prawduct guides and reviews; it never implements → conforms; this is prawduct's own skill surface"
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk touches a reviewer write path or the Critic data plane"
      - "prawduct is Python and must never be specific to Python → conforms; no gate, canary or language dispatch is touched, and the preference row is language-neutral prose in a template every product gets"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms, and Chunk 02 REMOVES a write: submit-or-nothing deletes the local-capture fallback, so the failure path stops writing a backlog item into the product"
  - artifact: data-model
    dispositions:
      - "every issue written to the backlog store conforms to the issue standard's §1 title rules on every write path → conforms; the title refusal is Wave A's and Chunk 02 does not touch it. The skill's obligation is the mirror image: compose a title in the `[prawduct] <component>: <symptom>` convention (design §2) so the send arm has nothing to refuse"
      - "a governance document reaches a terminal state; it is never deleted → conforms. The drop-box VRF's stale bullets are CORRECTED in place, not deleted, and the drop-box itself is untouched — §7's lockstep retires it in Wave C, and the reports already sitting in `incoming-bugs/` still need triage until then"
      - "`backlog_service_repo` selects which backlog store is authoritative → conforms and is not stretched; `report-bug` reaches the pinned constant, and a product with the scalar unset can still file"
      - "facts are immutable and append-only → inapplicable; Wave B writes no fact"
      - "derived views are disposable and never authoritative → inapplicable; Wave B adds no view, and no gate reads either chunk's output"
      - "a fact written by a newer schema than the reader is a loud block → inapplicable; no schema changes. Adjacent and already true: the outbound marker carries its own `v: 1`, so a future block format is a receiving-side reader problem"
      - "governance verdicts are computed from the fact ledger, never model-written state → inapplicable; no chunk touches the Critic data plane. Worth stating because Chunk 02 sails close to it: the L1 recomposition IS model judgment, and it lives in the `report-bug` skill (a decision) and never in `lib/backlog/` (the data plane) — the same G1 split Wave A recorded"
      - "two stores, two lifetimes → conforms, and Chunk 02 tightens it by subtraction: submit-or-nothing removes the local-capture write, so the failure path stops leaving a committed backlog item behind for an upstream bug"
partition: serial — 02 rewrites the caller that 01's preference row governs, and both edit the same consent story
last_validated: 2026-09-07
---

## Requirements Confidence

**Level:** High

**Why:** Wave B schedules two things an owner-approved design already fixes exactly.
`documentation/backlog-service-upstream-filing.md` §4.1 pins the preference's three states, its
default, and each state's adapter behavior; §7.1–§7.2 pin the `report-bug` rewrite step by step and
the preference row it depends on. Wave A built and reviewed the whole data plane those two sit on.
Nothing here is being derived.

**Open assumptions / unknowns:**

`[ASSUMPTION: Wave B lands WITHOUT the [XP6 verify] step, which becomes a release-gating operator
verification rather than a chunk gate | MED impact | user can veto]` — XP6 (current GitHub
non-collaborator label behavior, on a throwaway issue) needs a second GitHub identity that is not a
collaborator on `brookstalley/prawduct`. The owner is a collaborator, so it cannot be verified from
this account and it is an owner lead-time item. It does not block: the payload is **already
label-less** by design §2, so XP6 can only *confirm* that choice or *widen* the receiving-side
intake query (§6, Wave C). It cannot change a byte that Wave B sends. Chunk 02 records it as a VRF
entry so it gates the release the way this repo gates every other owner-eyeball item, instead of
living in a handoff note that one `/clear` erases.

`[ASSUMPTION: prawduct's own Upstream filing row reads ask-user (the default), not never-file | LOW
impact | user can override]` — `never-file` here is tempting and is the wrong call. `send()` runs
`check_preference` **before** `check_not_self`, so a `never-file` row in this repo would replace the
`self-file` refusal with `filing-disabled` — and `self-file` is the refusal that names the right
remedy (*prawduct's own bugs are filed with `add`*). The mechanical guarantee is unchanged either
way, because the self-file check refuses independently; only the diagnostic differs, so the row
keeps the better one. The row is still worth writing: it makes the three states discoverable in the
repo that defines them.

`[ASSUMPTION: the drop-box stays live through Wave B | LOW impact | user can override]` — design §7
retires `incoming-bugs/` **only together with** the MG5 advisory repoint, which is Wave C. Wave B
therefore lands the replacement and leaves the drop-box's receiving side alone; the reports already
in it still need triage.

**What would raise confidence:** N/A at High. The one genuinely open question (XP6) is named above
and is scheduled rather than assumed away.

## Status

- [x] Chunk 01: The consent preference becomes authorable, and the code stops saying it isn't
- [x] Chunk 02: `/prawduct:report-bug` files upstream, and every surface describing the drop-box write stops
Context: **Wave B is complete, 2026-09-07 — both chunks built, reviewed and closed.** The cumulative
review returned 0 blocking, 11 warnings and 3 notes; thirteen were fixed in one round and the
backlog-reconciliation note was accepted. What Wave C inherits from that round is one obligation and
one reminder, both here because a handoff note is gitignored and this file is not:

- **The `untriaged-upstream-reports` repoint is now load-bearing, not just tidy.** Until it lands,
  issue-side triage is manual and the skill says so in as many words — a framework session that
  drains only the drop-box has drained the channel that no longer grows. The repoint's query shape
  is design §6, and it is only correct if VRF-018 confirms a non-collaborator cannot apply a label.
- **#194 (BKL-7Q4M) and #234 close with this branch.** #234 is the drop-box lockstep guard whose
  replacement went live here and whose retirement is Wave C's own work. Recorded as the accepted
  disposition on `rev-20260907T223417Z-f6ec097a`. **Corrected 2026-09-08:** the close happens *at
  the merge*, not in the Wave C commit — this repo is on the Issues backend, where `status --to
  shipped` closes over the API the moment it runs and leaves an item wrongly closed if the PR is
  reworked (#697). `/prawduct:pr`'s Merge Flow is what runs it.

**One accepted observation is owed to the next commit that touches
`tests/preferences/test_no_upstream_content_egress.py`**, and it is recorded here rather than only
in the gitignored handoff because a deferral nothing durable names is a drop:
`test_no_command_block_passes_a_composed_field_as_a_shell_literal`'s docstring summary and its
assertion message both still enumerate "`--title`/`--component`" after `--body` joined the class.
**The fix is deleting the enumeration from both, not extending it** — a list in prose beside a list
in code is what went stale. It gates nothing and was not worth a review round of its own; it costs
nothing riding a commit that file is getting anyway. **Discharged 2026-09-08 in Wave C Chunk 02**,
which took that file deliberately rather than waiting for a commit it happened to get — the enumeration
is gone from both, and the sibling `test_the_skill_names_no_drop_box_write_path` lost its
mention-vs-write carve-out in the same pass, since the channel it carved out for is retired.

**Chunk 01 complete, 2026-09-07.** The row ships in the template, so `init-product` writes
it into every product it scaffolds, and `never-file` is reachable by editing a line. Review returned
0 blocking; its two warnings and one note were all fixed in the same commit rather than dispositioned
— all three priced free or rode files already dirty. Two things Chunk 02 should not re-derive: the
preference reader is unchanged and needs nothing further (the row was the whole gap), and a claim
about the world ("no product has this row yet") had FOUR carriers across two modules and two test
files — when Chunk 02 falsifies "report-bug writes a drop-box file", grep the claim, not the file.

Plan written 2026-09-07, Wave B of the BKL-7Q4M program (A = the adapter, shipped at
`40b772b2`; B = this; C = the MG5 drop-box retirement and the `untriaged-upstream-reports` repoint).
The owner ruled 2026-09-06 that the release cuts **after all three waves**, so this plan does not
close the release either. The owner ratified the Local-first surface-vs-site clarification on
2026-09-07 — it is no longer a pending veto, and Chunk 01 records that.

Riding Chunk 01's commit, deliberately: `.prawduct/learnings.md` (+1 rule, 296) and
`learnings-detail.md` (+1 narrative), edited on `develop` and carried onto this branch. A
bookkeeping-only commit must not land on the integration branch, and `check-learnings-pairing`
reads `ok` — the pairing is not broken and must not be "fixed".

## Scaffolding

Not applicable — this is a change to an existing, scaffolded project. `pytest tests/ -q` is the
suite; `python3 plugin/bin/prawduct-hook` is the CLI under test.

### Verification Strategy

Two things beyond the suite, because both chunks ship *instructions a model follows*, and a green
test proves the text exists rather than that it leads anywhere.

- **Chunk 01** — run `prawduct-hook init-product` into a throwaway directory and read
  `read_filing_preference` against the result. The freshly-onboarded repo is the real input, and the
  learning this repo already paid for (`learnings.md`: a fixture encodes your belief about the
  input, so it confirms only that belief) says the test must read the shipped template rather than a
  hand-written row.
- **Chunk 02** — walk the rewritten skill as a model would, start to finish, against the fake
  transport: compose a payload, preview it, read the digest back, approve it, watch the fake record
  a create. Then walk it again with the preference at `never-file` and confirm the flow stops at the
  refusal with nothing written and no local capture attempted.

## Build Chunks

### Chunk 01: The consent preference becomes authorable, and the code stops saying it isn't

- **Description:** `Upstream filing: ask-user | always-file | never-file` becomes a row an operator
  can actually write. Today the reader handles all three states and only one is reachable, because
  no preferences file anywhere has the row — the reader's absent-file branch is the whole of
  production. This is a thin slice through the same layers Chunk 02 widens: template → onboarded
  product → reader → adapter behavior.
- **Depends on:** none
- **Artifacts consumed:** `documentation/backlog-service-upstream-filing.md` §4.1 (the three states,
  the default, each state's adapter behavior) and §7.2 (the row, mirroring `PR merge strategy`)
- **Deliverables:**
  - `plugin/templates/project-preferences.md` — the `Upstream filing` row in `## Workflow`, in the
    house bullet form (`- **Name**: value (default: … — why)`) the reader's regex already parses.
    Value `ask-user`; the parenthetical carries what each of the other two states means and that
    `never-file` is a hard refusal. No Enforcement-table row: that table ships empty on purpose.
  - `.prawduct/artifacts/project-preferences.md` — this repo's own row, `ask-user`, with the
    `self-file`-diagnostic reason from the assumption above. The Enforcement/norm row this repo
    already carries for upstream filing (the XP7 contract row) needs no change.
  - `plugin/lib/backlog/upstream.py` — the comment above `PREF_ASK_USER` saying the row is
    *"authored in Wave B, and until it exists every read here resolves to the default"*. It becomes
    false in this chunk; the *reason* the default leans `ask-user` is what must survive the edit.
    Also drop the `Chunk 02` anchor at `:961` — a chunk number names no plan and renumbers.
  - `tests/test_backlog_upstream.py` — the real-template test, and the `Chunk 02` anchor at `:463`.
- **Tests:** the shipped `templates/project-preferences.md`, read through `core.TEMPLATES_DIR` and
  fed to `read_filing_preference`, resolves to `ask-user` with **no** warning — pinning the artifact
  and the predicate against each other so neither can move alone. Same assertion against this repo's
  own `.prawduct/artifacts/project-preferences.md`, which is a governed product's real row. The
  existing fixture-based state tests stay as they are; they cover values the shipped rows do not.
- **Acceptance criteria:** `pytest tests/ -q` green. A directory freshly built by `init-product`
  parses to `ask-user`. Editing that one row to `never-file` makes `file-upstream` refuse with
  `filing-disabled`, and to `always-file` waives the digest comparison and nothing else — both
  reachable now by editing a file rather than by writing a fixture.
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=upstream-report-bug`, no `release=`)
  3. The owner's Local-first ratification recorded on the `[DECISION: …]` in `architecture.md`
     § Direction — the entry currently reads as awaiting a veto that has now been withheld
  4. `/prawduct:critic` run and blocking findings resolved
  5. Committed (carrying the two learnings files) and chunk marked `[x]` in Status

### Chunk 02: `/prawduct:report-bug` files upstream, and every surface describing the drop-box write stops

- **Description:** The skill stops writing a gitignored file on one machine and starts filing an
  issue a maintainer will see. Design §7.1 step by step: step 3's drop-box write becomes
  L1-recompose → `file-upstream` preview → (under `ask-user`) show the exact payload + the
  confirm-synthetic prompt on any code block → approve → send. Step 4's inert fallback loses its
  local capture — submit-or-nothing (§5) — and keeps the tracker pointer. `Found in:` is unchanged
  and still sourced from `prawduct-hook version`, never recalled.
- **Depends on:** Chunk 01 — under `ask-user` the flow is identical either way, but `never-file` has
  to be a row a reader can actually have set before the skill can honestly say it honors one.
- **Artifacts consumed:** `documentation/backlog-service-upstream-filing.md` §2 (the outbound bytes),
  §3 (L1 recomposition — soft, model, never the data plane), §4.2–§4.3 (the L2 review, the
  code-block gate, the unattended rule and its honest limit), §5 (the two-call recipe and the
  refusal set — **read the current list; it is six refusals as of `2412be64`, not five**), §7.1
- **Deliverables:**
  - `plugin/skills/report-bug/SKILL.md` — the rewrite, including the frontmatter `description:`,
    which still advertises the drop-box and is what a model reads when deciding to invoke at all.
    Section 1 (is this a prawduct bug or a product bug) is unchanged and stays first. The skill
    **cites** §5 and §2 rather than restating them.
  - The same file's receiving-side section — one sentence that new reports now arrive as issues;
    the `incoming-bugs/` triage steps stay, because that backlog is real until Wave C.
  - `plugin/skills/backlog/adapter-mode.md` (~`:289`) — *"that skill has not been rewritten onto it
    yet — it still writes a local drop-box file, so nothing calls this op."* False the moment this
    chunk lands. The absence guard cannot catch it: it fires only on lines that name the op, and
    that sentence names none. **This deliverable is the durable record of that.** The
    *"do not call it yourself"* instruction to the backlog skill is still correct and stays — what
    changes is who the caller is.
  - `.prawduct/operator-verification.md` — the drop-box-retirement VRF (~`:418`) has two bullets that
    this chunk falsifies, and both are prose an owner will act on: it expects an
    `untriaged-upstream`-**labeled** issue (design §2 files **label-less**, which is the whole XP6
    question), and it expects the no-channel fallback to *"degrade cleanly to local capture"*
    (§7.1 removes the capture; the pointer is what remains). Corrected, not deleted.
  - `.prawduct/operator-verification.md` — a new VRF for `[XP6 verify]`: file one throwaway issue
    from a **non-collaborator** GitHub identity into a public repo, and record what labels that
    identity can and cannot set. Owner-only, blocked on an identity this account does not have, and
    it gates the release rather than this chunk.
  - Tests: an instruction-surface assertion that the skill names the two-call recipe and instructs
    no drop-box write — the mechanical half of §7's lockstep, so Wave C cannot land a retirement
    while a caller still writes there, and this chunk cannot silently keep the old path.
- **Tests:** the instruction-surface assertion above; the fake-transport end-to-end walk in
  Verification Strategy as an integration test where it is cheap to express.
- **Acceptance criteria:** `pytest tests/ -q` green. Following the rewritten skill end-to-end against
  the fake transport files exactly one issue and records exactly one create. Under `never-file` the
  flow stops at `filing-disabled` with nothing written and no local backlog item created. With no
  `gh` identity it stops at `auth` and offers the tracker pointer. No surface still says `report-bug`
  writes to `incoming-bugs/`.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Change-log entry added (`scope=upstream-report-bug`, no `release=`)
  3. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Chunk 02's `cumulative`
makes the branch PR-ready; `/prawduct:pr create` runs when the user asks.

- **After Chunk 01** — the trajectory check this plan actually needs: with the row authored, is
  `never-file` a *hard* guarantee end to end, or only inside `send()`? The reader, the check, and
  the row have never been exercised together before this chunk.
- **After Chunk 02 (cumulative)** — full-bundle. The question for it: after this, a model-invocable
  skill can reach an irreversible write into a foreign public repo. Everything mechanical about that
  was built in Wave A; what Chunk 02 adds is the *instructions*, and instructions are the layer the
  Critic reads worst. Weight the review toward the skill text.

## What Wave A learned that this plan is built on

Wave A's fourteen review findings shared one shape: **every one was a claim about a PATH that was
true of the codebase generally.** A guard existed; it did not cover the case it was written for. A
transform was reused without the pairing that made it safe. So the standing question for both chunks
is not *is there a guard* but *what does this guard cover* — and for Chunk 02, whose deliverable is
prose, the same question reads: *what does this sentence tell a model to do when the happy path
doesn't hold?*
