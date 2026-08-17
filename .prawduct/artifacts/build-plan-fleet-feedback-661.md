---
artifact: build-plan
version: 2
scope: fleet-feedback-661
branch: fix/661-fleet-feedback
depends_on: []
last_validated: 2026-08-17
---

## Requirements Confidence

**Level:** High

**Why:** The requirements are four defect reports in issue #661, each independently
verified against `develop@bbc31ed` before planning — three by reading the mechanism,
one (the chunk parser) by executing the regex against the failing inputs. Problem,
success and scope are each statable in one sentence per chunk. The reporter supplied
reproduction conditions and file:line for every claim.

**Open assumptions / unknowns:**

- [ASSUMPTION: `update-gitignore` should keep mutating by default | LOW impact | user can override]
  `/prawduct:doctor` calls it as a *repair* step, so mutate-by-default is the
  intended contract. The reported harm is that `--dry-run` was silently *accepted*
  while mutating — fixed by rejecting unknown flags and by implementing `--dry-run`
  for real, not by inverting the default.
- [ASSUMPTION: the version stamp belongs at the archive boundary, not on every
  reflection paragraph | MED impact | user can override] `.session-reflected` is
  appended by the agent in free prose with no code write site; the one code-owned
  write is the `/clear` archive into `reflections.md`. Stamping there covers the
  whole corpus the reporter analysed with one write site.

**What would raise confidence:** Nothing blocking. Chunk 03's suppression behaviour
(does the never-onboarded advisory outrank its downstream consequences, or sit
alongside them?) is a design call recorded in that chunk rather than an unknown.

## Status

- [ ] Chunk 01: Chunk-heading parse failures become loud, not empty
- [ ] Chunk 02: Unrecognised flags are refused; `update-gitignore` gains a real `--dry-run`
- [ ] Chunk 03: An enabled-but-never-onboarded repo says so, by cause
- [ ] Chunk 04: Reflections carry the version that produced them
Context: Plan written 2026-08-17 from issue #661 (external fleet report, ~840 entries
across 10 governed repos). All four chunks are independent — different files, no shared
contract — and are built in parallel by worktree-isolated subagents, then combined,
suite-run and E2E-verified by the main agent. Per user direction subagents run only
their own feature tests; the full suite and all end-to-end verification are the main
agent's. Next: dispatch the four subagents.

## Verification Strategy

Feature level (subagents): each chunk's own pytest module, run in isolation.

End-to-end (main agent, after combining): the full suite, plus live exercise of each
fixed path against this repo — parse a plan carrying every heading form, invoke
`prawduct-hook` with a bogus flag on both an argv and a no-argv command, run the
advisory sync against a synthesised un-onboarded fixture repo, and drive a real
`/clear` archive to confirm the stamp lands in `reflections.md`.

## Build Chunks

### Chunk 01: Chunk-heading parse failures become loud, not empty

- **Description:** `_CHUNK_HEADING_RE` cannot match `### [ ] Chunk 1` (the checkbox
  occupies the position the regex expects `Chunk`) or any dotted id such as
  `Chunk 1.2` (`(\w+)` excludes `.`, so the id terminates before `_CHUNK_ID_SEP`).
  Neither case errors; both yield zero deliverables, and zero is indistinguishable
  from "nothing to check." One fleet repo hit this four times across v3.1.1→v3.3.4,
  each time reading a silent green. The module already applies the opposite rule
  elsewhere — `incompleteness_reason` and `_has_unfinished_chunk` both refuse to
  read an unparseable plan as complete — so this is bringing one matcher into line
  with a contract the module already states twice.
- **Depends on:** none
- **Artifacts consumed:** issue #661 comment 1 (`buildplan_refs.py:171`)
- **Deliverables:** widened id pattern and checkbox tolerance in
  `plugin/lib/buildplan_refs.py`; a detector that distinguishes *a heading that
  names a chunk but did not parse* from *no chunk heading present*, reported loudly
  by the consumers of `_chunk_section_lines` rather than returned as an empty list
- **Tests:** unit — every heading form in the wild (`### Chunk 02:`,
  `## Chunk 2 (RES-K3QP) —`, `### **Chunk A** —`, `### [ ] Chunk 1:`,
  `### Chunk 1.2:`) parses; a malformed heading raises/reports rather than
  returning empty; a plan with genuinely no chunk headings still returns empty
  quietly (the two must stay distinguishable)
- **Acceptance criteria:** all five heading forms parse to their ids; an
  unparseable `Chunk` heading produces a signal the caller cannot mistake for
  a pass; no existing plan in `.prawduct/artifacts/` changes its parse
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Unrecognised flags are refused; `update-gitignore` gains a real `--dry-run`

- **Description:** `cmd_update_gitignore` takes no `argv` parameter at all
  (`prawduct-hook:4680`), so no flag can reach it — `--dry-run` is not discarded by
  arg parsing, there is no arg parsing, and the reconcile *runs*. Its sibling in the
  same `/prawduct:doctor` flow, `cmd_coverage_scaffold` (`:4328`), does take `argv`
  and is `--apply`-gated. The asymmetry is in the signatures, which is why no naming
  convention separates the two groups. The reporter triggered a live mutation by
  passing `--help`. `cmd_verify_operator_verification` has the same shape one step
  removed: it takes a positional `vrf_id`, so a flag is silently read as data.
  Two fixes, in this order: refuse unrecognised arguments at the dispatch site so
  the hole cannot reopen per-command (the precedent is `_check_binary_skew`, placed
  before dispatch "so it covers every command"), then give `update-gitignore` the
  `--dry-run` its siblings taught users to expect. Mutate-by-default is retained —
  doctor calls it as a repair step — so this closes the surprise without changing
  what doctor does.
- **Depends on:** none
- **Artifacts consumed:** issue #661 body item 1 + comment 1 (`prawduct-hook:4680`, `:4328`, `:6054`)
- **Deliverables:** argument validation covering every subcommand in `_dispatch`
  (`plugin/bin/prawduct-hook`); `--dry-run` preview support in `cmd_update_gitignore`;
  rejection of flag-shaped input where a positional is expected in
  `cmd_verify_operator_verification`
- **Tests:** unit — a bogus flag on a no-argv command exits non-zero with a message
  naming the flag; a bogus flag on an argv-taking command does too; every real
  subcommand still accepts its documented arguments; `update-gitignore --dry-run`
  reports what it would change and leaves `.gitignore` byte-identical; without the
  flag it still reconciles
- **Acceptance criteria:** no subcommand silently ignores an argument it does not
  understand; `--dry-run` on `update-gitignore` mutates nothing; `/prawduct:doctor`'s
  existing repair behaviour is unchanged
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: An enabled-but-never-onboarded repo says so, by cause

- **Description:** Enabling the plugin starts the hooks immediately, and the hooks
  write runtime state into `.prawduct/` — `.session-start`, `.advisories.json`,
  `.prawduct-version` and more. So `.prawduct/` fills up, the banner shows a version
  and advisories appear, while `CLAUDE.md` carries no `PRAWDUCT:ANCHOR` and
  `project-state.yaml` is still a stub. Every visible signal says installed and
  working; gates then run green against a null product definition. A live fleet repo
  has been in this state for weeks. Three advisories fired there and the word
  "onboard" appears nowhere in any of them — prawduct detected three downstream
  *consequences* of never having onboarded and never named the cause, which is worse
  than silence because visible activity reinforces the belief that setup succeeded.
- **Depends on:** none
- **Artifacts consumed:** issue #661 comment 2
- **Deliverables:** new `plugin/lib/onboarding_probes.py` following the sibling
  probe modules' `register()` shape, registered in
  `plugin/lib/probe_families.py::register_all`; the advisory must state the cause
  and the remedy (`/prawduct:onboard`), and must distinguish *never onboarded* from
  *onboarded and drifted* so a session does not prescribe a repair for a repo that
  needs an install
- **Tests:** unit — fires when the anchor is absent and `project-state.yaml` is a
  stub; silent for a fully onboarded repo; silent for an onboarded repo that has
  merely drifted (anchor present, state populated); the two negative cases are the
  load-bearing ones
- **Acceptance criteria:** a synthesised un-onboarded fixture produces an advisory
  naming onboarding as the cause; this repo (onboarded) produces none
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Reflections carry the version that produced them

- **Description:** Nothing in the write path stamps the running prawduct version, so
  grouping learnings by the version that produced them has to be reconstructed from
  inline dates — the reporter could attribute only 35.6% of 839 entries across 10
  repos, and the rest is an honest `unknown`. `.session-reflected` has no code write
  site (the agent appends prose), but its archive into `reflections.md` at `/clear`
  does: `prawduct-hook:717`. Stamping there covers the whole corpus with one write
  site and converts the reporter's archaeology into a query, permanently and for
  every repo running prawduct.
- **Depends on:** none
- **Artifacts consumed:** issue #661 body ("The finding")
- **Deliverables:** a provenance header (running version + ISO date) written ahead
  of each archived reflection block in `plugin/bin/prawduct-hook::cmd_clear`, using
  the existing version accessor rather than a second one; the existing archive
  failure contract is preserved exactly — a stamp must never be the reason a
  reflection is lost
- **Tests:** unit — an archived block carries the version and date; an archive into
  an existing `reflections.md` keeps the separator contract; a version that cannot
  be resolved degrades to an honest marker rather than omitting the header or
  raising; the `UnicodeError`/`OSError` preservation path still keeps the file
- **Acceptance criteria:** a real `/clear` archive lands a stamped block in
  `reflections.md`; an unresolvable version does not break the boundary
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
