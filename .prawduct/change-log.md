# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

<!-- Older entries live in .prawduct/change-log-archive/YYYY-MM.md, moved there verbatim by `prawduct-hook archive-change-log`. -->

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

## 2026-10-02: develop opens 3.7.0-dev.4

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.0-dev.4 | release=v3.7.0 -->

The dev track's version moves from `3.7.0-dev.3` to `3.7.0-dev.4` in the four carriers, so repos on
the develop track pick up `record-lint-945-939` (#946). The public changelog's rolling notes gain its
consumer-facing summary, which that PR did not carry. Owner-directed, 2026-10-02.

## 2026-10-02: record-lint stops flagging out-of-repo refs; the PR entry probe refuses retired tag keys

<!-- prawduct: type=bugfix | scope=record-lint-945-939 | release=v3.7.0 -->

Two record-lint defects that the sibling-repo audit of 3.7.0-dev counted as review cost.

**#945, false `chunk-ref-missing`.** `_looks_like_file_path` treated three non-repo token shapes
as deliverable paths: absolute paths (a binary on a remote host), `~/` paths, and the repo's own
`owner/repo` slug. A correct plan therefore drew a BLOCKING finding. These were 12 of the 61
blocking findings on 3.7.0-dev. **Root cause:** the predicate excused only the slash-command form
of a leading `/` and had no answer for a slug, so it fell through to "path". **Fix:** a token
anchored at `/` or `~` is not a repo path. That rule covers slash-commands, so the narrower
carveout is gone. A slug is excused only when git names it as the GitHub `owner/repo` of a
configured remote, read once per repo from `git config` and parsed by the existing
`parse_remote_url`. It is not decided by shape, so `docs/api` and other repos' slugs stay
checked.

**#939, retired `chunks=` and `status=` keys on new tag lines.** The parser still accepts both
for history, and nothing told an author they are dead. The PR reviewer caught three
recurrences. **Root cause:** no check read the added tag lines. **Fix:**
`change_log.RETIRED_TAG_KEYS` is the one list of retired keys, and `retired_keys_on` reads it.
On a tracked log, the PR Step 1c entry probe refuses a retired key with `retired-key`, reading
only the tag lines the branch adds or edits. Step 1c is where the entry is written, after the
last Critic review, so a record-lint check would have run before the entry existed and caught
none of the recurrences. It was built and dropped in this change. Untouched historical entries
still parse and are never flagged. CL4 in `governance-artifact-lifecycle-requirements.md` is
amended by owner ruling to allow the probe's one tag read.

## 2026-09-30: develop opens 3.7.0-dev.3

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.0-dev.3 | release=v3.7.0 -->

The dev track's version moves from `3.7.0-dev.2` to `3.7.0-dev.3` in the four carriers, so repos on
the develop track pick up `sibling-hook-perf` (#938). The public changelog's rolling notes gain its
consumer-facing summary, which that PR did not carry. Owner-directed, 2026-09-30.

## 2026-09-30: four governance frictions found in consumer transcripts

<!-- prawduct: type=bugfix | scope=sibling-hook-perf | release=v3.7.0 -->

Found by the same investigation of consumer sessions as #931.

**A process running on its own no longer reads as a reason for `DO NOT CLEAR` (#932).** The
`clear-verdict` gate fired nine times across fabulous, discodon, puzzles and this repo. Every
block was correct and each cost a turn. The cause was one belief: that a server or recorder the
session had started would die with a `/clear`. The digest's precedence line, the verdict paragraph
in `session-hygiene.md`, and the gate's own message now say that a clear ends the conversation,
not the process. Tests pin all three places: the digest and `session-hygiene.md` in one, the gate
message in another. The digest pays for its clause in place by
dropping an opening sentence that restated "Read on demand", so both injected totals fall and
their ceilings ratchet down.

**Telemetry labels a repo by its identity, not its directory (#933).** Discodon's devcontainer
mounts every workspace at `/opt/venv`, so every ledger event since 09-21 read `project: "venv"`.
`gitstate.project_label` is now the one owner, shared by the ledger and the review-stats header.
It tries, in order: the committed `product_identity.name` (as a slug), the push remote's
repository name (so a lone remote not named `origin` counts), the main checkout's directory (which a worktree shares), and only then the
directory itself. `gitstate.declared_product_name` becomes the one reader of
`product_identity.name`, and the briefing delegates to it.
`[DECISION: clones of one repository share a label | identity is what the committed name and the origin carry, and no path survives a container | this changes future labels for three checkouts: samsung-frame-art-loader becomes curatarr (its origin), fabulous-tips becomes fabulous, and prawduct-learning becomes prawduct; worktrees take their main checkout's name; existing rows are not relabelled]`

**`**Type:** bugfix` parses (#934).** `building.md` sizes governance by work type (feature,
bugfix, refactor, …), and authors carried the word into a chunk's `Type:` field, which reported
it as unknown on a chunk that ran as `code` anyway. The work types are now aliases for `code`,
the full protocol, so an alias can never lighten a review. `planning.md` names them. Aliases are
case-sensitive, like the types: `Bugfix` is reported as unknown, as `Code` always was, and the
error now lists the aliases beside the types.

**The code-without-tests canary check is deleted (#935, part of #164).** It fired on every
session that changed code without a test file, a research spike under `docs/` included, and it
could not recognise test files beyond Python and JS naming. #164, owner-ruled, deletes it with
Critic Goal 1 as its covering surface. `_is_test_file` goes with it, and `architecture.md`'s
retroactivity inventory no longer lists it. The surviving canary checks had no tests at all; they
have them now, including a control showing that the canary still runs when the deleted check
would have been its only finding. The rest of #164 is still open.

## 2026-09-30: hook latency no longer grows with the evidence store

<!-- prawduct: type=bugfix | scope=sibling-hook-perf | release=v3.7.0 -->

**Root cause (verified by profile and A/B).** Every SessionStart and Stop composes a coverage
verdict whose free-edge search keys every tree the evidence store mentions, one `git ls-tree`
each. The keys were memoised only within the process, and the store is append-only and shared by
every worktree, so hook latency grew with the store's age rather than with the work at hand. On a
snapshot of the puzzles repo (231 trees), each cached plugin version from 3.5.1-dev.2 to
3.7.0-dev.2 took about 6.4 s per Stop, of which 4 s was this keying. Field data from the
transcripts shows the growth: the puzzles Stop p90 went from 3 s to 15 s as its store grew from 20
trees to 231 between 09-12 and 09-30, and discodon (1,743 trees) reached a p90 of 62 s (#931).

**Fix.** `lib/tree_key_memo.py` persists each computed key beside the evidence store, keyed by the
tree and by `verdict_cache.code_identity()`. That is now the one identity both per-clone memos
use: the plugin version, a checkout's plugin tree and the content of its uncommitted edits, and the
bytes of the modules that decide judgeability and form the key. The last two parts came from the
boundary review. A same-version install and a second edit to an already-dirty file would
otherwise have replayed keys formed by older code, and those could grant a free edge. Each tree now
costs one `git ls-tree` per clone and per code change. A save that fails is reported once and is
not retried. An unreadable tree
is never remembered, so it still denies the free edge and is asked again next time. A second
cost of the same kind: trees that git has collected, which the store keeps naming, cost a failed
`ls-tree` apiece on every hook (198 of 1,326 here). One `git cat-file --batch-check` now answers
all of them (`evidence.missing_objects`, reached through the key function's `prime`). The memo
saves every 100 new keys and at exit, so a cold run that the harness kills keeps its progress.

Measured on the same snapshot, with an edit before each Stop as in a real session: warm Stop hooks
went from about 6.0 s to about 2.1 s, and the coverage verdict itself from 4.1 s to 0.05 s, with
identical gate output. This repo's warm Stop went from 34 s to about 6.3 s. The rest is a fixed
set of git calls spread across other gates, plus the base-advance diagnosis's per-candidate diffs,
filed separately.

**SessionStart's api-versioning probe (#936).** `Codebase` ran an `rglob` per pattern, four per
sync, each descending into `.git`, `.venv` and `node_modules` before discarding what it found. It
now walks once, pruning the skip set as it descends, and every scan filters that listing: about
1.1 s down to 0.18 s on the snapshot, returning exactly the same files as before on puzzles and on
this repo.

## 2026-09-29: develop opens 3.7.0-dev.2

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.0-dev.2 | release=v3.7.0 -->

The dev track's version moves from `3.7.0-dev.1` to `3.7.0-dev.2` in the four carriers, so repos on
the develop track pick up `opus-55-w6-reference-docs` (#926). Owner-directed, 2026-09-29.

## 2026-09-29: the reference docs are retuned for Opus 5.5 (audit wave W6)

<!-- prawduct: type=feature | scope=opus-55-w6-reference-docs | release=v3.7.0 -->

Wave W6 of `opus-55-prompt-audit-2026-09.md`, ruled in full on 2026-09-28, and the audit's last.
It applies slice E's 19 decisions to `plugin/docs/`. `runbook-authoring.md` no longer calls length
the best-evidenced finding in the literature, which its own evidence section contradicted, and
drops five competing superlatives (E-1, E-6). Its three self-review passes become the bar a
finished runbook meets; the subtraction pass stays (E-5, F3). Dated model statistics, a volatile
benchmark and the guide's research history give way to the rules they supported (E-7 to E-9).
`norms.md`'s enforcement table points at § Severity instead of restating it as "ratified", the
threshold the Critic protocol had already dropped in W3 (E-4), and loses a correctness proof and
three history clauses (E-3, E-10 to E-13). `waivers.md` loses its argument against the retired
per-rule literals and no longer names a region form it does not parse (E-14, E-15).
`test-report-contract.md` stops addressing prawduct's maintainers and trims the reviewer-talk
comments consumers paste (E-2, E-16, E-17). `governance-telemetry.md` and `discipline.md` lose
ticket ids, audit citations and row history (E-18, E-19). The runbook skill's three copies of
E-5's self-review instruction are aligned with the guide. No parsed table changed shape, and no
token ceiling applies to these files.

The Fable final-coherence pass the audit owed ran over the whole cycle (W1 to W6) before this wave
lands, and its fixes ride here. It found seams between waves, not disagreements of intent. The
chunk-boundary review exception in `session-hygiene.md` and root `CLAUDE.md` now allows for a short
plan's single boundary review. `review-cycle.md` no longer quotes a `building.md` sentence that is
gone, or claims the close directive prints its paragraph verbatim. The backlog skill names the
change-log's `release=` tag, not the inert `status=shipped`. Two pointers to a nonexistent
"Coverage Evidence" section, and the preferences template's Goal 4 for norms (it is Goal 3), are
corrected. The pr skill loses its issue ids, and the backlog and janitor skills their pointers to spec decisions D4 and D14. A `reviews.md` rule loses its
whole-diff self-scrub, and a `core.md` Tell no longer assumes file-list deliverables. The
methodology index drops its between-phase validation (B-19's class), and three reviewer directives
in `critic_consolidate.py` lose their capitals, as A-5 did for NEXT-ACTION.
`review-cycle.md`'s and the injected footprint's ceilings ratchet down with their readings.

## 2026-09-29: develop opens 3.7.0-dev.1

<!-- prawduct: type=chore | scope=dev-track-bump-3.7.0-dev.1 | release=v3.7.0 -->

The dev track's version moves from `3.6.2-dev.7` to `3.7.0-dev.1` in the four carriers, so repos
on the develop track pick up `opus-55-w5-operational-skills`. The track now heads for a minor
release rather than a patch. Owner-directed, 2026-09-29. It rides this PR.

## 2026-09-29: the operational skills are retuned for Opus 5.5 (audit wave W5)

<!-- prawduct: type=feature | scope=opus-55-w5-operational-skills | release=v3.7.0 -->

Wave W5 of `opus-55-prompt-audit-2026-09.md`, ruled in full on 2026-09-28. It applies slice D's
61 decisions to every skill except `critic` and `pr`. Doctor states "degraded because ungraded"
once instead of seven times, and its checks keep their statuses and lose the history of why each was
built (D-1 to D-8, D-30 to D-33). The migration scrub keeps every command, gate and ordering and
loses its incident stories, version pins, spec ids and a misplaced, duplicated `duplicate_alias`
remedy (D-9 to D-14, D-35 to D-40). The backlog files drop an envelope no code emits (D-15),
prohibitions naming retired ops, and second copies of facts that have a home elsewhere (D-24, D-25,
D-45, D-51). `add` lists delegation last (D-26, F4). `pick` ranks by value per effort and flags
unassessed items, where it used to compute a score (D-28). The janitor points at
`/prawduct:methodology` instead of a product `CLAUDE.md` that no longer carries planning guidance
(D-18). Shouted headings lose their caps (D-54, D-58, D-61). The runbook skill and template lose
their copies of the overstated "best-evidenced finding" claim and the dated hallucination rate
(E-1, E-8). The backlog half was built by one worktree delegate. D-23's and D-29's maintainer
rationale moved into test docstrings, and D-29's two sentence asserts went with it. The
writable-block-field guard follows D-25's moved sentence to `adapter-mode.md`, and was
red-verified there. One regression probe (D-28, Opus 5.5) found no regression. No token ceiling
moved, because no file in this wave has one.

Two changes are more than prose. The janitor's neglected-hygiene check (Backlog Health check 5)
now runs on the Issues backend too, over `in-progress` rows whose `working_branch` appears merged;
it had been off there since #529 (now #729), which has shipped. And a test now checks the
cache-query grant on all four readers of the backlog cache (two agents and two skills), where before only the PR
reviewer's grant was tested.

## 2026-09-29: the methodology guides and templates are retuned for Opus 5.5 (audit wave W4)

<!-- prawduct: type=feature | scope=opus-55-w4-methodology-templates | release=v3.7.0 -->

Wave W4 of `opus-55-prompt-audit-2026-09.md`, ruled in full on 2026-09-28. It applies slice B's
decisions to the six methodology guides and the artifact templates: B-1 to B-40 except B-41, a
flag. The guides no longer license ending a turn with work in hand (B-9, B-16, B-35): a chunk
boundary ends the turn only when the plan is done, the next chunk needs the user, or the cycle
has reached what one review covers. The builder is no longer told to scrub its own diff while the
Critic runs, to review every artifact phase, or to redo a delegate's sweep (B-1, B-19, B-36,
B-10 to B-12); instead a delegate's brief asks for the output that shows a removal or sweep
complete. Delegation stops being the default for tangents and no longer requires a subagent for a
consumer grep (B-2, B-13 to B-15); the delegate criterion is the owner's, wall clock gained
without conflict. Chunk shape, file-list deliverables and phase choreography become advice
(B-17 to B-19), which closes #341. `architecture.md`'s "goals bind; method is advice" norm
therefore moves from `in-transition` to steady-state: its stopgap goes, and its Retroactivity
line records the migrated sites. B-21 and B-22, discovery's domain-concern table and question
quotas, were held until a Sonnet 5.5 probe and ship here. On the probe, the new text raised every
critical concern the old text raised. Templates lose dead component headers, unnamespaced
commands, incident stories and caps-lock register (B-3 to B-7, B-29 to B-32, B-37, B-38). The
build-plan template's worked example states deliverables as outcomes, and its cadence line points
at the short-plan rule. The template half was built by one isolated-worktree delegate. Carried
from the W3 handoff: `building.md`'s fix-order sentence takes W2's register, and a delegate brief
names the budgets its files sit under. Token readings drop on five guides. `delegation.md` rises
by 14, a recorded raise. The fix-order pin now asserts `gates.FIX_ORDER` verbatim, the suite-at-boundary pin follows
its de-bolded sentence, and
`docs/discipline.md`'s anchors for rows 4 and 9 follow B-2 and B-24. The template
`project-state.yaml` loses the removed question quotas, its version fossils, and a claim that
the backlog probes were unbuilt. The owed Sonnet 5.5 probes
ran through `claude -p`, because the Agent tool's alias cannot select that model:
- W3's reviewer surfaces showed no regression.
- B-12 is the first decision whose control failed and whose treatment fixed it.
- The longer early-stop probe on Opus 5.5 did not stop early, even on the pre-W1 text. The audit
  records what that means for per-wave probing.

Also shipping:
- The scaffolded backlog legend's `closed-by:` names a scope, branch or release tag, never a bare
  chunk id (B-5), which closes #779. `documentation/backlog-system-requirements.md` takes the
  same fix.
- `reflection.md`'s stopping rule and its bug-fix protocol are compressed into one statement each
  and point at Step 3, rather than restating it.
- `authoring.md` gains a learning: a new project-wide concept cascades to the product anchor, the
  Critic and PR protocols, methodology, templates and their budget tests.

Two departures from the owner's ruled text, both vetoable (the plan's cumulative-review record):
- R-7: B-25's replacement dropped the 3-4-file size, which decides whether a Critic review runs.
  It is restored as small.
- R-10: B-24's "file the rest" contradicted `core.md`'s fix-the-class rule. Post-Fix now fixes
  the class through its one owner when it can be changed here.

Plan: `build-plan-opus-55-w4-methodology-templates.md`.

## 2026-09-29: develop opens 3.6.2-dev.7

<!-- prawduct: type=chore | scope=dev-track-bump-3.6.2-dev.7 | release=v3.7.0 -->

The dev track's version moves from `3.6.2-dev.6` to `3.6.2-dev.7` in the four carriers, so repos
on the develop track pick up `opus-55-w3b-review-cycle-split`. Owner-directed, 2026-09-28. It rides
this PR.
