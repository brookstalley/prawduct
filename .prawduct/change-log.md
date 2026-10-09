# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

## 2026-10-09: a SAFE TO CLEAR that cites the message is refused

<!-- prawduct: type=fix | scope=self-citing-clear -->

- **The `clear-verdict` Stop gate refuses a `SAFE TO CLEAR` whose reason is the turn itself**
  (#977). Before, the gate caught only `YOUR TURN`/`COMPLETE` with `DO NOT CLEAR`. That was
  checked by running a red case, which passed straight through. So "the questions are in this
  message" relied on recall, and the wave-1 trial missed it in 2 of 7 agents. `standing_block.self_citation`
  matches the reason paragraph narrowly. It looks for the message, reply, response or turn named
  as where something is or what holds it, or for something said to sit above or below. A reason
  that names a durable record (notes, a commit, a file, an issue), or denies that anything lives
  only in the message, passes. Tuned on this machine's transcripts: 15 of 1,252 `SAFE TO CLEAR`
  closes match, and each reads as a genuine instance. The refusal costs one rewritten line. No
  new gate id: it joins the gate's recorded NFR exception, whose text now names it.

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
