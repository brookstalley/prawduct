# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-10-19: boundary test evidence is recorded from the Testament pool

<!-- prawduct: type=chore | scope=testament-evidence -->

- #1020, closing #1016's last acceptance item. brookstalley/testament#52 gave `testament run` a
  JUnit report, so the first `test_commands` entry is now `testament run --junit-xml {junit_xml}`
  and `prawduct-hook test-evidence record` ingests the pool's run. The pytest half took about a
  minute on the pool, against about 7.5 minutes locally (measured 2026-10-19).
- The pool selects out tests it cannot run, so on its own it would have recorded a subset as the
  suite. A third entry runs exactly those here: `requires_history` (one test), and a new sibling
  marker, `requires_local_cache`, on `TestSilentAgainstThisRepo`, whose full assertion needs this
  clone's backlog cache and which skipped on every runner. Counts reconcile with the local run:
  9,145 passed and 17 skipped either way. `.testament.toml` deselects both markers.
- Checked live, not inferred:
  - Pool unavailable: a runner restart mid-run made testament fall back to this machine, and the
    recorder took that run.
  - No result: testament exits 2 and deletes the report, and the recorder refuses with exit 2 and
    writes no evidence.
  - Partial report: the recorder's existing per-command rule covers it. A non-zero exit with no
    failing test in the report is refused, and testament's `population_mismatch` is exactly that.
- `documentation/running-tests.md`'s "Evidence still comes from the recorder" section, stale since
  testament#52, is rewritten as "Recording evidence".
- Recording now needs `testament` installed (any command that cannot start fails the record).
  `running-tests.md` and the README say so, and name the by-hand route for a machine without it:
  run pytest and the node suite, then pass both reports to one `record --from-junit` call.

## 2026-10-19: v3.7.1 is cut, and develop reopens on 3.7.2-dev

<!-- prawduct: type=chore | scope=release-v3.7.1 -->

**27 scopes and 27 change-log entries. `K = 0`, so this took the whole-develop promotion path with
nothing withheld.** Tag `v3.7.1` was published with the CHANGELOG section as its Release notes.
`check-released v3.7.1` reports 3 of 3 verified, and the hand-dispatched `verify-release` run and
the tag-push run are both green. To re-derive the scope set, grep for `release=v3.7.1` in
`change-log.md` and `change-log-archive/`.

**A patch, by owner decision over the agent's 3.8.0 recommendation.** The alignment pass and the
default-on `clear-reason` gate matched the minor-tier precedent. The owner chose the ratified
conservative-versioning norm instead. `.prawduct/artifacts/release-plan-v3.7.1.md` records both
sides. Two field-bug PRs merged ahead of the cut (#1018 for #1011, and #1019 for #217, #1004,
#1005 and #1006). The cut wrote consumer notes for ten scopes the open CHANGELOG section did not
name, archived 13 shipped plans, and moved 18 shipped entries into `change-log-archive/2026-10.md`.
Step 11a's suite run on the prep tree was green the first time.

## 2026-10-17: backlog file writes only to its own repo, and says when it filed

<!-- prawduct: type=bugfix | scope=backlog-file-path | release=v3.7.1 -->

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
  list. Reading agrees: `encode.label_has_prefix` is the one label-prefix match, case-insensitive
  except for prawduct-minted `id:` aliases, and decode, `is_prawduct_issue`, the status
  reconciliation, `update`'s facet and tag swaps, `reconcile-labels`' foreign/ours split
  (`provision.facet_of`) and `restructure`'s kind relabel all go through it, so a hand-made
  `Source:Review` is no longer reported as foreign and relabeling `Kind:Bug` no longer leaves a
  duplicate kind; `stage` and `status` values decode to their vocabulary spelling. So
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
- The suite now passes when an agent runs it from its own worktree. Tests that assert on all of
  `prawduct-hook`'s stderr (empty, or its first line) used to inherit the checkout running the
  suite, so in a `.claude/worktrees/agent-*` tree the hook's linked-worktree NOTE landed on
  stderr and four of them failed. They now run the hook through one helper,
  `tests/fixtures/hook_env.isolated_hook_run`, which points the project and `cwd` at a directory
  the test owns and pins the plugin root, so neither environment notice applies; a positive control
  shows a real stderr line still reaches the assertion.
- Not in this change, filed as follow-ups: #1013, the same own-target rule for the id-addressed
  writes (`comment`, `update`, `status`, `link`), whose target resolves from the issue id inside
  `core`; and #1014, a label-length preflight for `import`, which today shares #1004's failure.

## 2026-10-18: a norm field written inline after the bold statement is a field

<!-- prawduct: type=bugfix | scope=norm-inline-why | release=v3.7.1 -->

- #1011. `- **Statement.** Detail. *Why:* reason.` read as no norm at all: every field matcher
  anchors at a logical line's start, so `norm-registry-unratified` told a product with ratified
  norms that none existed, and record_lint's `governed_by` count and dead-why were blind to
  the same entries. `norm_probes._direction_scan` now splits such a line at the
  marker, so every matcher reads it as the line-start form. The split is bounded to avoid
  minting entries from prose: only inside a bullet opening with a bold statement, only at a
  sentence start (right after the statement, or after `.` `!` `?` `;`), and `Status:` never
  opens one — a roadmap bullet saying "Status: blocked" stays a roadmap item.
  Accepting the inline form is the owner's decision (2026-10-18, on #1011's triage: adapt to
  how authors write, but avoid false positives), the same call as emphasis (2026-08-03) and
  blockquotes (#637).
- record_lint's `direction_norm_count` now delegates to `norm_probes._direction_norm_count`
  instead of walking raw text over a shared regex. That walker diverged from the probes twice
  (blockquotes, then inline fields), each time because only the reader feeding the probes got
  the tolerance.
- The advisory names its cause: "`## Direction` sections exist, but no entry in them carries a
  field" versus "no artifact has a `## Direction` section". The evidence string is unchanged,
  so the advisory id — and any dismissal — carries over. One existing test asserted the old
  wording and was rewritten to the new contract, with the reason in its docstring.
  `docs/norms.md` § Anatomy states the inline form.

## 2026-10-17: prawduct's suite can run on the Testament pool

<!-- prawduct: type=feature | scope=testament-onboarding | release=v3.7.1 -->

- #1016. `.testament.toml` and `docker/testament.Dockerfile` onboard this repo to Testament
  (`../testrouter`): container executor, CI's pytest suite with the `dev` extra resolved fresh
  (`uv.lock` is gitignored here), release tags shipped to runners (`[git] tags`). `documentation/running-tests.md` carries
  Testament's agent block, plus a paragraph saying evidence stays with `prawduct-hook
  test-evidence record` until brookstalley/testament#52 gives `testament run` a JUnit report.
  AGENTS.md points to it in one line rather than carrying it: AGENTS.md is injected into every
  session and the block cost ~390 tokens over the framework footprint ceiling. The pointer is paid
  for by cutting the Reference list's `plugin/docs/principles.md` entry, which repeated the
  Principles section; the footprint stays at its recorded 3108. `docker/` joins the packaging
  test's not-distributed directories.
- The first pool runs (2026-10-18, after the owner's allow) corrected two assumptions. The setup
  required `uv.lock`, which this repo gitignores on purpose, so it now resolves the `dev` extra
  fresh as CI does. And 195 tests failed with `python3` not found: hook tests launch it under a
  minimal `PATH` (`/usr/bin:/bin`), and the slim image has Python only in `/usr/local/bin`, so the
  image links it into `/usr/bin`. Then: 9014 tests, all passed or skipped, none missing, over
  `gpu-bozeman` and `laptop`, in 2:08 cold and 1:13 warm, against 9.5-13 min for the local suite.
  The tests' summed durations are 14.3 min, so most of a local run's wall clock is overhead (#1015).
- A runner's checkout has no history. Running the suite in a history-less single-commit copy found
  one test that needs it (`test_scaffold_rows_match_the_shipped_history`, which searches history
  by content and fails rather than skips without it). It is marked `requires_history` (registered
  in pyproject) and selected out of the Testament command; plain `pytest`, the evidence recorder's run and CI
  still run it.

## 2026-10-17: upstream-report triage names the query that lists its set

<!-- prawduct: type=bugfix | scope=upstream-intake-enumeration | release=v3.7.1 -->

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

<!-- prawduct: type=bugfix | scope=post-discovery-friction | release=v3.7.1 -->

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

<!-- prawduct: type=feature | scope=agents-md-anchor | release=v3.7.1 -->

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

<!-- prawduct: type=bugfix | scope=empty-verify-rounds | release=v3.7.1 -->

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

<!-- prawduct: type=bugfix | scope=consolidate-trigger | release=v3.7.1 -->

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

<!-- prawduct: type=feature | scope=critic-tree-unchanged | release=v3.7.1 -->

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
