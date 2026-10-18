# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-10-17: backlog file writes only to its own repo, and says when it filed

<!-- prawduct: type=bugfix | scope=backlog-file-path -->

- #217, #1004, #1005, #1006: four fixes on the `backlog file` path, picked as one bundle.
- **#217.** `file` accepted any well-formed `--repo`, and the backlog skill pre-grants
  `backlog file --*`, so an agent could create an issue as the user in a foreign public repo
  without a prompt. `upstream.check_own_target` now refuses (`foreign-target`, exit 2, not
  retryable) unless `--repo` matches the identity `resolve_self_identity` derives from
  `backlog_service_repo` or the `origin` remote, case-insensitively; an unresolved identity
  refuses too. It runs before any request, attended or unattended. `file-upstream` stays the
  only cross-owner route.
- **#1004.** `encode.check_enum` refuses any facet value whose `<facet>:<value>` label exceeds
  GitHub's 50-character limit, naming the flag and the maximum, so a long `--source` no longer
  dies as an opaque 422 on the labels endpoint. `update_item` now runs that check with its other
  offline validation, before any request: it used to run after the title/body PATCH, so a refused
  facet left the item half-updated.
- **#1005.** `provision._create_missing` matches existing labels case-insensitively, as GitHub
  does, and a create refused with `validation` re-lists once and counts a label that now exists
  as existing (the race with another writer). `ensure_labels` returns `applied`, the requested
  names in GitHub's existing spelling, and every caller that applies labels after provisioning
  (`file`, `update` facets and tags, `status`, alias restore, both import paths) applies that
  list. Reading agrees: `encode.facet_labels` is the one facet-prefix match, case-insensitive,
  and decode, `is_prawduct_issue`, the status reconciliation and `update`'s facet and tag swaps
  all go through it; `stage` and `status` values decode to their vocabulary spelling. So
  `--area docs` on an item carrying `area:Docs` neither re-adds nor strips it, and an item whose
  only status label is `Status:In-Progress` reads as in progress. The L1 fake now refuses a
  case-variant label create, as GitHub does. `encode.label_fits` is the one label-length rule,
  shared by `check_enum` and `validate_tags`.
- **#1006.** A successful human-mode `file` prints `filed <id>: <url>` first, stdout is flushed
  before stderr is written (a piped stdout is block-buffered, so lint lines used to arrive above
  the outcome), and ok-envelope lint lines read `lint (advisory, the write succeeded): …`.
- Tests that filed into a fake `octo/repo` from this checkout now run from a directory whose own
  tracker is that repo (`fakes.fake_github.own_tracker`); their assertions are unchanged except
  the two pinning the old `lint:` spelling. The gated live smoke test runs from a work tree whose
  own tracker is `$BACKLOG_LIVE_REPO`, since it would otherwise refuse its own `file` calls.
- Not in this change, filed as follow-ups: #1013, the same own-target rule for the id-addressed
  writes (`comment`, `update`, `status`, `link`), whose target resolves from the issue id inside
  `core`; and #1014, a label-length preflight for `import`, which today shares #1004's failure.

## 2026-10-17: upstream-report triage names the query that lists its set

<!-- prawduct: type=bugfix | scope=upstream-intake-enumeration -->

- Found while triaging five upstream reports: `backlog list --untriaged` returned 0 while the
  `untriaged-upstream-reports` advisory counted them. Both readings were right about their own
  predicates — `--untriaged` lists issues with no prawduct label *and* no `prawduct:` body block,
  and every `file-upstream` report carries a provenance block, so it is in scope with no `stage`.
  The intake procedure counted a set and named no command to list it, so the nearest-named one
  was used and answered a different question.
- `skills/report-bug/SKILL.md` § Receiving side now names `cache-query unstaged` (filtered to
  `[prawduct]` titles) and says why `--untriaged` cannot show a report; `adapter-mode.md`'s
  `--untriaged` paragraph says the same from the other side.
- Three spec passages (data model §3, security model F7, API §9) described `--untriaged` as
  selecting on labels alone and therefore a superset of quarantine that never misses an anonymous
  filing. The code also excludes blocked issues, so that claim was false; they now state the real
  predicate and that a blocked unlabeled filing surfaces through `cache-query unstaged` instead.

## 2026-10-16: the first governed session after an onboarding discovery opens clean

<!-- prawduct: type=bugfix | scope=post-discovery-friction -->

- Field report from a newly onboarded product, which opened its first governed session to an
  oversized-state warning, a strategy-artifact notice nobody had framed, a handoff offered as
  context that held only a file list, and a skill path an agent resolved one directory too high.
- **Template.** `templates/project-state.yaml` was 29 KB, 26.6 KB of it comments, mostly the
  optional-key reference. That prose moved to `docs/project-state-keys.md` (content kept, recast as markdown), reached as
  the new `/prawduct:methodology project-state` topic. The template keeps a one-line hint per
  key and is now under 12 KB. The learnings one-line-rule carrier moved with the prose. The
  topic stays out of the digest roster rather than spend the digest's reserved headroom.
- **Existing repos.** `oversized_state_probes` gains a bullet, matched on lines found only in
  the shipped key reference, saying those copied blocks can go. Comments a repo wrote never match.
- **Handoff.** `briefing.NO_FORWARD_NOTE_HEADING` is now the single source for the heading,
  used by both the generator and the boundary pointer. The pointer names a handoff with no
  forward note as a machine record and does not offer it as context.
- **Onboard.** The discovery close writes `.prawduct/.handoff-notes.md` before recommending
  `/clear`, because that session started ungoverned and never received the rule that carries
  work across a clear. The note frames the strategy-artifact advisory as planning's agenda.
- **Paths.** `skills/methodology/SKILL.md` states that bare plugin-relative paths in the guides
  resolve against `${CLAUDE_SKILL_DIR}/../..`. The build-plan ref check no longer reads a
  variable-rooted token like that one as a missing file (`buildplan_refs._looks_like_file_path`).

## 2026-10-14: the governance anchor lives in AGENTS.md; CLAUDE.md imports it

<!-- prawduct: type=feature | scope=agents-md-anchor -->

- #942, under the owner's rulings on #942 (2026-09-30) and #928 D-8 (2026-10-10), plus two
  answers given in session on 2026-10-14 (the Claude Code line lives inside the `AGENTS.md`
  block; an existing product `CLAUDE.md` keeps its own text).
- **The anchor moves.** `STATIC_ANCHOR` is reworded for any host, with one Claude Code line and a
  rule for a host that cannot tell whether its integration is loaded (assume it is not).
  `migrate_plugin.plan_governance_anchor` decides every write — the anchor into `AGENTS.md`, the
  import into `CLAUDE.md` — with each file's exact new content; the writer executes that plan,
  the `reanchor` preview prints it, and the grade offers a repair only when it completes the
  layout, so the three cannot disagree. `CLAUDE.md` gives up its anchor only when `AGENTS.md`
  takes it; symlinks out of the pair are never written through, and two names for one file keep
  one anchor and no self-import. When the plan cannot finish, migrate refuses before touching
  anything and onboarding warns, each naming the owner's fix. The shipped-anchor archive moved
  to its own leaf module, `anchor_archive.py`.
- **The repair moves fleets.** `anchor_repair` grades the pair, with new `legacy-layout` and
  `import-missing` statuses; `ANCHOR_V5` (the 3.6–3.7 anchor) joins the archive; the `reanchor`
  preview lists every file it would write with the exact bytes (`writes` in `--json`). Doctor
  Health Check #4 describes each status.
- **Every reader knows `AGENTS.md`.** Root `AGENTS.md` is protected (`agents-md-edited`); the
  onboarding probe, the briefing's size check and critical-rules read, and `jurisdiction`'s corpus
  all read it. The batch-fix directive called `.md` under `agents/` free to write mid-review,
  though `agents/` is protected; it now names every protected path, checked against the set.
- **This repo moved too.** Its contract is in `AGENTS.md`, and `CLAUDE.md` is `@AGENTS.md`.
- A decision is recorded under `architecture.md`'s reconciled-files norm; the norm's wording is
  left for the owner to amend. The #928 requirements doc's header and inventory rows 29 and 30
  are updated.

## 2026-10-13: stop buying verify rounds that have nothing to verify

<!-- prawduct: type=bugfix | scope=empty-verify-rounds -->

- In sibling repos on 3.7.x, 20–24% of `verify-resolutions` rounds had no open blocking or warning
  finding to verify, against about 5% before (part of #724). Three causes, three fixes:
- **An owed boundary review counts as a later review.** `critic_mode.review_owed_after` now owns
  "a later review will cover this": a later chunk's review, or the plan's boundary `cumulative`
  when the last chunk is `Type: cumulative-final` or the plan is short. The Stop gate's deferral,
  `cost-of-commit` and the review close read it. Inference on an uncommitted cumulative-final last
  chunk answers `deferred` instead of running a `final` the cumulative would repeat, and the Stop
  gate's note for that chunk asks the same question, so it stops saying "then cumulative" once the
  cumulative has run.
- **A verify pass can confirm an observation fix.** A resolution may name a prior observation's
  `O-n` id in the existing `finding.fid` slot; only `fixed` is accepted for one, and gates never
  read it. `stats` stops counting such a round empty, and the census reports the fix as `fixed`.
- **A verify pass reports observations only about the fixes it verifies.** In
  `verify-resolutions` an observation must carry `about: {review_id, fid}` naming the prior finding
  or observation it judges; one without it is dropped (counted on the fact as
  `observations_dropped`), never refusing the round. The dispatch directive no longer invites
  open-ended style observations, which drove a fix → verify → new-observation treadmill.

## 2026-10-12: the ledger records which path consolidated a Critic review

<!-- prawduct: type=bugfix | scope=consolidate-trigger -->

- Three paths reach `consolidate()` — the `SubagentStop` hook, `critic-consolidate`, and the Stop
  hook's self-heal — and they left identical state, so a dead hook covered by the backstop looked
  like a working one (why the bare-matcher defect hid for seventeen days; #182). `consolidate()`
  now takes a required `trigger` that each caller sets (`subagent-stop`, `explicit`,
  `session-end-backstop`), never inferred inside it, and an unknown value raises before anything
  is read. `ledger-append` requires `--trigger` for `review.critic`, refuses it for `review.pr`,
  and writes it as the `trigger` envelope key. `explicit` does not split the skill's own call
  from a human's: both run the same CLI, and a flag the skill passed to say so is one a human
  could type too, so the split would not hold. VRF-002 only needs hook-or-not.
- Two readers, so the field is not write-only. `review-stats` gains `consolidated_by` (report
  schema 7 → 8): Critic reviews per path, every path listed even at zero, so a dead hook shows as
  `subagent-stop 0` in a routine report rather than only to someone who opens the ledger. And
  VRF-002, which was blocked on this, now takes its verdict from `trigger` instead of from findings
  merely appearing; it still needs the live run on a released plugin.

## 2026-10-10: consolidation refuses a review during which the tree changed

<!-- prawduct: type=feature | scope=critic-tree-unchanged -->

- A reviewer's `Bash` patterns and `Write` paths are a contract the harness does not enforce, and
  nothing checked that a review left the product alone (#992, part of the #928 R-8 parity bar).
  `critic-begin` now records the whole working tree in the manifest as `dispatch_tree`, and
  `critic-consolidate` compares it with the tree it finds. Any change outside prawduct's own
  session files (`core.GITIGNORE_ENTRIES`, read with gitignore's anchoring) refuses the review and
  names the paths. The partials stay on disk.
- A diff cannot say who made a change, and `review-cycle.md` asks the builder to prep while a
  review runs, so the refusal is not final. The main session can consolidate with
  `--tree-changed-by-builder "<reason>"`, which writes the paths and the reason into the review
  fact and `.critic-findings.json` (owner ruling 2026-10-10). The SubagentStop hook and the
  session-end backstop never pass the flag. So a session that edits after an unconsolidated review
  is now blocked at Stop until it attests.
- The PR review payload gains a `review_tree_changes` section listing the attested paths and
  reasons for the reviews the branch's coverage rests on (via a new `prior_review_ids` key in the
  coverage composition), and `review-protocol.md` tells the PR reviewer to judge each attestation
  against the paths it covers.

## 2026-10-10: ad-hoc delegates are dispatched with harness isolation, not pointed at a worktree

<!-- prawduct: type=fix | scope=delegate-isolation-dispatch -->

- `methodology/delegation.md` told the coordinator to create a delegate's worktree and point the
  agent at it. That shape does not hold: the harness keeps no Bash `cd` between calls, and a skill
  forks in the session's own directory. So the delegate's commits and reviews landed in the
  coordinator's checkout and reported success (#791, merged into #221). The guide now dispatches in
  the background with `isolation: "worktree"`, and the coordinator writes the brief into
  `.claude/worktrees/agent-<id>` from the launch result. The delegate stays on the harness's
  scratch branch, where `prawduct-hook` already refuses `.prawduct/` writes, so the no-governance
  rule is enforced rather than requested. `building.md` points there, and a test pins the shape and
  the reason.
- #221's marker-and-guard design is superseded rather than built. Probes on Claude Code 2.1.296
  showed forked skills already follow `EnterWorktree` and isolation, so the guard would have added
  a hook and a per-write check for a failure that no longer reproduces.

## 2026-10-10: a measured study of governance cost against quality

<!-- prawduct: type=docs | scope=governance-roi-study -->

- `.prawduct/artifacts/governance-roi-study-2026-10.md` reports a study over the owner's and a
  collaborator's 42 repos. It combined a blind, independently verified Opus review of recently
  merged code, a git-only rework detector, and classifications of what caused each fix and
  rewrite. Governed and ungoverned work showed no detectable difference in defect density (ratio
  1.25, CI 0.66-2.38) or in throughput. 46% of escapes could have been caught by code review.
  Late requirements are the largest cause of rework, and about 4 in 5 non-fix rewrites could not
  have been prevented by asking up front. Follow-ups: #984, #989, #986, and the dated re-run #987.
- The tooling is in `.prawduct/research/escape-2026-10/`. `test_escape.sh` is the detector's
  known-answer test, `build_batches.py` and `branch_landings.py` rebuild the study's inputs byte
  for byte, and `stats.py` re-derives every computed number in the artifact. Every repo except prawduct is anonymised.
  The raw data stays off this public repo, because it describes private code.

## 2026-10-09: a corrupted-store test no longer races git maintenance

<!-- prawduct: type=fix | scope=test-git-maintenance-race -->

- `tests/test_critic_dispatch_refusal.py` failed once in CI on PR #982 with a `FileNotFoundError`
  on `.git/objects/maintenance.lock`. Every `git commit` starts a detached
  `git maintenance run --auto`, and `test_an_uncomputable_diff_never_refuses` changes the
  permissions of every file in the object store, so the lock could vanish mid-walk. The file's
  `_init_repo` now sets `maintenance.auto=false` before the first commit. No other test walks
  `.git/objects`. A `conftest.py` setting would not reach this file, because its git calls run
  with a closed environment.

## 2026-10-09: a SAFE TO CLEAR that cites the message is refused

<!-- prawduct: type=fix | scope=self-citing-clear -->

- **A new Stop gate, `clear-reason`, refuses a `SAFE TO CLEAR` whose reason is the turn itself**
  (#977). Before, only the `clear-verdict` gate read the close, and it caught only
  `YOUR TURN`/`COMPLETE` with `DO NOT CLEAR`. A red case confirmed that: "the questions are in this
  message" passed straight through, so the rule relied on recall, and the wave-1 trial missed it
  in 2 of 7 agents. `standing_block.self_citation` matches the reason paragraph narrowly. It looks
  for something said to be *in* the message, reply, response or turn ("are in this message",
  "exists only in this reply"), the turn said to hold it, or something said to be above or below
  at the end of a clause. "Nothing changed in this turn" passes, and so does a reason that names a
  durable record (notes, a commit, a file, an issue), or cites the message only inside a
  denying clause ("No open question is in this message"). `tools/measure-self-citing-clear.py` re-derives the tuning. Read 2026-10-09, it matched
  18 of 1,533 `SAFE TO CLEAR` closes on this machine, each a genuine instance on reading. It has
  its own gate id so its firings count apart (`stats` → `stop_blocks.by_gate`) and the version
  banner announces it. The NFR records its expected yield.

## 2026-10-09: the review judges against goals, the brief stays current, and the pass is measured

<!-- prawduct: type=methodology | scope=requirements-alignment-w2 -->

- **The boundary review judges the work against its goals** (#975; Critic Goal 5). It reads the
  plan's Goals and the brief's near-term and North Star, not only the chunks. Work that drops or
  alters a goal the owner stated is a dropped requirement (BLOCKING). A goal still marked inferred
  is a WARNING naming it. The plan's mid-build decisions reach the owner in one NOTE, with what
  settled each and any alignment-pass miss, and from there into the PR description. `reflection.md`
  names a mid-build decision the owner corrects as an alignment-pass miss. Trialled on a fixture
  (results in the plan's Trial section). The reviewer payload raise is declared with its price.
- **The brief reads as current and says who said what** (#974). An amendment rewrites the part it
  changes rather than appending. An inference keeps its plain-words mark until the owner confirms
  it. The template shows a line before and after confirmation.
- **The alignment pass's yield is committed** (#978): `tools/measure-alignment-yield.py` reports,
  per project and window, asked-before-build, mid-build questions and correction leads from
  transcripts. The audit's 24/138 came from a hand-selected subset and is not reproducible, so the
  script's own figures are the baseline: `tools/measure-alignment-yield.py --until 2026-10-09`
  (governed sessions, read 2026-10-09: asked first on 140 of 963 substantive requests; 349 mid-build
  questions; 18 correction leads). Each run also prints a health line (unparsed lines, transcripts
  with no owner turns), because a transcript format change shows up only as falling counts. Re-run near 2026-11-20 with `--since 2026-10-09`.

## 2026-10-09: the alignment pass — ask together, up front, then decide well alone

<!-- prawduct: type=methodology | scope=requirements-alignment -->

- **The Confidence Check becomes the alignment pass** (`building.md`). Before a plan exists the
  agent takes one of four responses, says which in a line, and the owner can catch a misreading
  before it is built: proceed; proceed citing a backlog item or spec; ask in one batch; or hold up.
  Hold up is for when the agent cannot form a reading worth correcting; otherwise it asks.
- **Mid-build decisions are durable-first** (`building.md` "Deciding Mid-Build"): do it right,
  match the product's other choices and the backlog, stop only for high stakes, prefer the durable
  choice, and record the decision in the plan's Goals.
- **Plans open with Goals** (`planning.md`, build-plan template, Critic Goal 2). They replace
  Requirements Confidence. The owner's words stay distinguishable from inferences, which are marked
  in prose rather than with `[ASSUMPTION]`. Older plans are still accepted.
- **Every governed repo hears it.** The session digest's rigor paragraph was rewritten in place
  within its reserve. Principles 6 and 20 and `discovery.md` now ask goal-shaping questions in one
  batch before building and never mid-build. The brief template gains a near-term goal and a North
  Star, and `discovery.md` says to ask which qualities of an owner's example matter before any one
  becomes a rule.
  `scope.accommodate` is now read where plans state their architecture goals, and the brief and
  project-state templates describe it as what every alignment pass keeps possible. Backlog `pick`
  notes that a ready item's pass is usually "proceed, citing it".
- **Retired vocabulary is tested out of live prose.** A test fails on Requirements Confidence,
  `[ASSUMPTION]` and the Confidence Check in plugin prose and the cross-cutting registry.
- **Trialled before shipping.** Six requests replayed from the 2026-10-08 transcript audit against
  fresh agents (results in the plan's Trial section). Budgets: `building.md` and the injected
  product-session text raised by declaration. The Critic files and reviewer payloads were ratcheted
  down.

## 2026-10-08: four field bugs for 3.7.1 — quoted `#`, api-versioning wording, scope examples, migrate activation

<!-- prawduct: type=bugfix | scope=field-bugs-790-813-765-915 -->

- **#790: a `#` inside a quoted scalar is data.** The advisory answer store cut every
  `project-state.yaml` scalar at its first `#` before unquoting, so `"ratified (#774)"` read back
  as `ratified (`. The same quote-blind split sat in `core.read_scalar_yaml_key` (every
  `read_str_yaml_key` caller: `active_build_plan`, `test_command`, …) and its inline mirror in the
  hook. All three now strip comments through one rule, `core.strip_scalar_comment`: a single
  quoted scalar keeps everything through its closing quote; otherwise a comment is a `#` that
  starts the value or follows whitespace, outside any quoted word. `foo#bar` now stays whole, as
  YAML reads it. The answer store also unquotes through `core.unquote_scalar` instead of a bare
  `strip("\"'")`. The issue's doctor/state workarounds never landed, so there was nothing to remove.
  Block-list and nested readers (`core.read_yaml_block`, the hook's list mirror,
  `coverage_probes`) still split at the first `#`; filed as #968.
- **#813: the api-versioning advisory counts the nested decision.** It said "records no versioning
  decision" to repos that had recorded one under `design_decisions.api_versioning_approach`, where
  the guides say to put it, because it read only the top-level `api_versioning_decided` scalar.
  `/prawduct:doctor`'s check already accepted either. The probe now reads the nested record from the
  raw file (a non-null value or an attribute block; `null`, `~`, a bare key, or the key at another
  level read as unrecorded), so either place resolves it and the two surfaces apply one rule. The
  evidence string is unchanged, so the advisory id, and every dismissal of it, holds.
- **#765: the change-log tag examples use a work-named scope.** The template and
  `lib/change_log.py` showed `scope=v1.4`, while the build-plan template declares `scope:
  pantry-v1` and a scope resolves to exactly one plan, so an entry copied from the example warned at
  release as work with no plan. The examples now use the build-plan template's scope, and a test
  pins that they agree.
- **#915: `/prawduct:migrate` checks that the plugin will load before it applies.** It never ran
  `check-plugin-active`, so a repo with no install record for its path was migrated, had its
  legacy hook stand down, and was told it was governed. The check now runs before the destructive
  apply, under a new `--context migrate` whose `inactive` wording names both readings (a
  `--plugin-dir` session whose repo is ungoverned once migrated, or a stale record for a worktree
  or moved checkout). An `inactive` result recommends installing first, the check's exit-0
  could-not-load NOTE routes to "not established", and the closing message claims governance only
  on `active`.

## 2026-10-08: develop opens 3.7.1-dev.2

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.1-dev.2 -->

The dev track's version moves from `3.7.1-dev.1` to `3.7.1-dev.2` in the four carriers, so repos on
the develop track pick up `junit-unreached-963-strip-code-966`. Owner-directed, 2026-10-08.

## 2026-10-08: test-evidence reads JUnit cases under any wrapper; learnings-migrate leaves code spans alone

<!-- prawduct: type=bugfix | scope=junit-unreached-963-strip-code-966 -->

- **#963: `test-evidence record` reads every `<testsuite>` and `<testcase>` in a JUnit report,
  under any wrapper.** The walk read only the root's direct children, so a case or a summary-only
  suite under any other wrapper (a `<testsuites>` nested inside the root, which merged CI reports
  produce) was never classified: a failure there recorded green and exited 0. The walk now
  descends through every element that is not a suite or a case, so it reaches all of them by
  construction rather than by a list of known wrappers. The reported shape — a failure two `<testsuite>` levels deep — was already counted, and a test now
  pins it. The same class one level in, also closed: a suite with no `<testcase>` (one that died
  before emitting any) nested inside a suite that has cases had its `errors=` ignored, because a
  populated suite was read by its leaves alone. Its outermost case-less suites are now read by
  their attributes too.
- **#966: `strip_links` tidies only the blanks a cut left.** #930 confined the tidy to lines that
  held a pointer, but on such a line it still ran over the whole line, so a code span beside the
  pointer lost the space before its punctuation (`ls -la .git` became `ls -la.git`). The tidy now
  removes only the blanks next to the removal marker when punctuation or the line's end follows.
  The patterns already take the blanks before a pointer, so nothing else needed them.

## 2026-10-08: develop opens 3.7.1-dev.1

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.1-dev.1 -->

The dev track's version moves from `3.7.1-dev` to `3.7.1-dev.1` in the four carriers, so repos on
the develop track pick up `learnings-migrate-punctuation-930`. The public changelog's rolling notes
gain its consumer-facing summary. Owner-directed, 2026-10-08.

## 2026-10-08: learnings-migrate tidies only the lines a removed pointer left

<!-- prawduct: type=bugfix | scope=learnings-migrate-punctuation-930 -->

#930: `strip_links` ran its post-removal tidy on every line, so it deleted whitespace before
punctuation (fusing commands in code blocks) and stripped trailing spaces (dropping Markdown hard
breaks) on lines that held no pointer. A mid-line metadata comment also ate its newline and joined
two rules, and both section writers right-stripped the last line's trailing spaces. Removals now
leave a marker and only marked lines are tidied; the writers strip newlines only; the metadata
comment body stops at its first close. The byte-accounting test cleans both sides with
`strip_links`, so it cannot see this class; a new `--apply` test compares against the raw source
through both the core and area writers.

## 2026-10-06: three bugs users hit — a product's own plugin, active plans, stale caches

<!-- prawduct: type=bugfix | scope=field-bugs-2026-10 -->

- **#959: a product that ships its own Claude Code plugin at `plugin/` can record reviews again.**
  The skew guard took any repo with `plugin/.claude-plugin/plugin.json` for a prawduct checkout,
  so every data-plane command refused there and pointed at a `prawduct-hook` that did not exist.
  A repo is now a checkout when that manifest names `prawduct`. When the manifest cannot be read
  or carries no name, the presence of `plugin/bin/prawduct-hook` decides, so a real checkout with
  a broken manifest still refuses a foreign binary. Both skew checks ask the one predicate.
- **#809 (and #960, merged into it): `archive-plan` and `plan-backfill --apply` archive a plan
  whose frontmatter says `lifecycle: active`.** The re-archive guard refused any `lifecycle:`
  value, and said the plan "has an end of life already". Only `completed` and `superseded` count
  now. The fix is in `read_completion`, the "does this plan record an end?" check, rather than
  in the guard alone, so any future caller of that check gets the same answer. Archiving replaces
  the old value, so the result carries one `lifecycle:` line.
- **#321: `prawduct-hook stale-plugin-caches` lists the prawduct cache versions no install
  uses**, in every config profile on the machine, with disk sizes and a delete command each. It
  deletes nothing. `/prawduct:doctor` Health Check #21 relays it as a recommendation that never
  grades the repo. A version counts as in use when any install record names its path, when a
  record whose path exists only inside a container names its version in the same profile, or
  when it is the plugin running the command. Profiles that share a cache through a symlinked
  `plugins/` are one entry. A profile whose record file, or any one record in it, cannot be read
  is reported ungraded with the reason, naming the record, and a cache that cannot be listed is
  reported rather than dropped, because an unreadable record might be the one protecting the
  version that profile loads. Doctor's scope now says it also covers the machine-level state
  prawduct's own install leaves (`docs/doctor-vs-janitor.md`).
  On the owner's machine it found 22 unused directories, about 154 MB, in 4 caches.
- **One reader of `installed_plugins.json`.** `plugin_activation.read_installed_plugins` reads and
  shape-checks the file for both `check-plugin-active` and the cache report; each checks the record
  fields its own question needs. `stranded_work.config_roots` gained a `holding=` argument so both
  of its callers find config roots the same way.

## 2026-10-04: aggregate-stats pools governance stats across products, contributed reports included

<!-- prawduct: type=feature | scope=telemetry-aggregate -->

The receiving end of the telemetry program (#262), and the collector's last criterion from #950.

- **`prawduct-hook aggregate-stats`** reads the products the operator names, never discovered ones.
  It turns each product's evidence store into the weekly reports `contribute` would build, so local
  and contributed reports share one shape and one definition of every metric.
- **Contributed reports** come from bundle files (`--bundles`) or the collector (`--collector`, the
  only path that opens a socket). Every line is re-validated against the allowlist, refused lines
  are counted, and a line written under a newer allowlist schema is counted apart as
  `schema_ahead`, never as refused. Duplicates are kept. A window a clone already sent is counted
  once.
- **Per plugin version**, never pooled across versions: reports by origin, weeks covered, volume
  bands, and each metric's `n`, median and trimmed mean, because bundle lines carry no identity.
- **The August design is replaced** (owner, 2026-10-03). It read ledgers and broke review cost down
  by mode and model after adding a `plugin` field to ledger lines. That field had no reader once the
  evidence store became the version-aware source, and `review-stats` already gives that breakdown
  per product.
- **Records:** the security model lists the bundle fetch as a fifth network site, and the collector
  entry in `project-state.yaml` states the #954 commitment to keep the workers.dev host live.
  VRF-023, the first live flush, is verified.

## 2026-10-04: a pruned review tree no longer turns the base-advance transfer into "could not run"

<!-- prawduct: type=bugfix | scope=transfer-pruned-trees -->

#956, and the secondary symptom #895 records. After a stacked branch's base merged,
`check-cumulative-critic` said the transfer check "could not run (a candidate tree could not be
diffed)".

- **Root cause:** the store outlives its objects. Dirty-tree review snapshots and rebased branches'
  trees are garbage-collected while the facts naming them stay, and this repo's store named 198
  such trees. Any one of them among the candidates made the whole check report that it never ran,
  even though it could never have granted.
- **Fix:** candidates git no longer holds are dropped in one `cat-file --batch-check` call before
  any diff. They still never grant. "Could not run" now means git could not say which objects it
  holds.
- **The stacked case itself is unchanged:** its reviews still do not transfer, so it reads as the
  ordinary `uncovered`. Letting it transfer is #895, and the denial's wording is #672.

## 2026-10-03: the stats collector, a Cloudflare Worker writing to R2

<!-- prawduct: type=feature | scope=telemetry-collector -->

Wave 3 of the telemetry program (#950), in `collector/`. It is built by isolated delegates, deployed
from the owner's account, and never shipped in the plugin.

- **`POST /v1/report`** admits only reports that pass the plugin's allowlist, which the worker
  embeds and a test pins equal to `plugin/lib/contribution_schema.json` (a separate
  `collector/schema.json` copy, read by nothing at runtime, was removed). It stores their canonical
  bytes as one R2 object each. It stores no IP, header or
  time beyond R2's own upload stamp.
- **A nightly cron** folds pending objects into one sorted bundle per UTC day and deletes them. It
  is idempotent across re-runs, crashes and overlapping runs. `GET /bundles/...` publishes them.
- **R2 direct rather than a Durable Object**, by owner decision (#950). A SQLite DO keeps 30-day
  point-in-time recovery that cannot be turned off, while R2 has no versioning and its deletes are
  irreversible.
- **Observability, logs, traces and Logpush are off,** pinned by a test.
- **The node suite runs in CI** as its own job and as the second entry in `test_commands`, so
  recording evidence here needs node.

## 2026-10-03: products can contribute anonymous stats, off unless their owner opts in

<!-- prawduct: type=feature | scope=telemetry-contribution -->

Wave 2 of the telemetry program (#949). The owner's condition (2026-10-03): "off by default and
consuming repos must affirmatively opt in".

- **`prawduct-hook contribute`** previews, as exact bytes, one report per settled ISO week and
  plugin version. Keys come from a committed allowlist; values are integers, stepped numbers,
  fixed-list values or volume bands. Metrics under their sample floor are left out.
- **`contribute --send`** sends only under the product's own `Stats contribution` row: `ask`
  with the previewed digest, or `always`. Every other state reads as `never` and refuses before
  the transport. The endpoint is a plugin constant, pinned to the deployed collector
  (VRF-022); an empty one refuses.
- **Delivery is at most once,** under a clone-wide lock. A window the collector provably did not
  store (refused, 503, a failed tunnel or handshake) stays pending; one that may have arrived is
  spent.
- **Surfaces:** the template ships the row unset; `/prawduct:janitor` asks once while it is unset;
  and the session briefing speaks only for an opted-in product, or for a row that is misspelled.
- **`prawduct-hook stats`** counts base-advance transfer grants apart from guard refusals, exports
  each severity's acted-on denominator, and says when a newer plugin's facts were left out.
- **Norms:** architecture's local-first rule and the security model's egress rule admit the upload
  as a third network surface, on the owner's recorded authority. The upstream-filing and
  contribution rows now share one row reader (`core.read_preference_row`).
- **Real-data check (the plan's verification strategy).** `contribute` over this clone's evidence
  store offers 13 reports, W31 to W38 of 2026. The only string values are volume bands, and the
  largest report is 535 bytes. No byte names a product, path, branch, scope or person. What a
  report does reveal is that some product ran a given plugin version that week, and a coarse
  activity profile. A collector operator could link a product's weeks by that profile, but never
  to an identity. That is the residual the audit accepted.
- **Also fixed (found by this branch's boundary run): a declared test command ending in a quoted
  argument was corrupted.** The YAML readers stripped quote characters from both ends of a value,
  so a command like `node --test 'dir/*.mjs'` came out with an unbalanced quote and
  `test-evidence record` crashed after the earlier suites had run. Now
  `core.unquote_scalar` and its hook mirror strip one pair of quotes only when they wrap the whole
  value, for both the scalar and the sequence readers. Every declared command is also split before
  any suite runs, and a bad one is refused with exit 2, naming it. The comment-truncation half of the
  same family stays #790.

## 2026-10-03: Stop blocks and sessions become evidence facts, and `prawduct-hook stats` reports cost and yield per plugin version

<!-- prawduct: type=feature | scope=telemetry-stats -->

Wave 1 of the telemetry program in `.prawduct/artifacts/roi-audit-2026-10-02.md` (#948). The
audit had to mine Claude Code transcripts for Stop-hook blocks because prawduct recorded none.

- **Stop blocks are now recorded.** A blocked Stop appends one `guard-refusal` fact per blocking
  gate (`guard` = `stop-gate:<id>`). It rides the class sink so that every control firing has one
  shape (#563's owner decision); a kind plugins in the field already know also keeps their
  verdict caches warm.
- **Session boundaries are now recorded:** a new `session-start` fact, observational, as the
  denominator for per-session rates.
- **`prawduct-hook stats` reports per plugin `major.minor`,** from the clone-shared evidence store:
  - **cost:** rounds per scope, measured-only review time, empty verify rounds, re-reviews, Stop
    blocks per session and by gate, and guard refusals;
  - **benefit:** findings by outcome, blocking fixed by goal, and red suite runs.
  Run over the ten sibling stores, it reproduces the audit's per-version counts of reviews, blocking
  findings raised and fixed, and re-reviews. `/prawduct:janitor` now runs it; its tool grant gains
  both spellings of `stats`.
- **Test changes.** The write-isolation test now skips the shared evidence store, the one write
  outside `.prawduct/` that the architecture norm admits. It skips nothing else, and no assertion
  was weakened.
- **Descoped:** learnings fired per session. Ledger lines carry no plugin version (#262 TEL1), so it
  cannot be bucketed by version.

## 2026-10-02: v3.7.0 is cut, and develop reopens on 3.7.1-dev

<!-- prawduct: type=chore | scope=release-v3.7.0 -->

**34 scopes and 35 change-log entries. `K = 0`, so this took the whole-develop promotion path with
nothing withheld.** Tag `v3.7.0` was published with the CHANGELOG section as its Release notes.
`check-released v3.7.0` reports 3 of 3 verified, and the hand-dispatched `verify-release` run is
green. To re-derive the scope set, grep for `release=v3.7.0` in `change-log.md` and
`change-log-archive/`.

**A minor, as the owner named it and v3.6.1 had already planned.** Three gates are stamped
`since: 3.7.0`; `.prawduct/artifacts/release-plan-v3.7.0.md` records the reasoning. The cut also
archived `waiver-pragma-plan.md`, a 2.0-line plan no sweep could reach because its `scope:` sat in
an HTML comment, as completed in v2.0.4 by a tree-content test.

Step 11a caught one red test on the prep tree: a README bullet saying "once per clone" read as a
clone claim to `test_plugin_absent_prose`, and was reworded before the prep commit.

`develop` reopens on `3.7.1-dev`, a patch guess per the runbook's guess-low rule.
