---
runbook: cut-and-publish-a-plugin-release
tier: 3
owner: prawduct maintainer
last_verified: 2026-09-13   # steps 0-22 executed end to end at the v3.5.0 cut, including step 10's
                            # rename and Phase 3, both of which were unexecuted before this run.
                            # Step 11a was ADDED during that cut, from two failures it caught.
                            # Steps 1-5 and 10 were REWRITTEN on 2026-10-19 for change fragments
                            # (#1012) and have not run in a real cut: the cut ran only on a copy of
                            # this repo. The next cut is their first execution.
                            # Phase 0's digest lines and steps 1-5, 10, 12, 20 and 22 were REWRITTEN
                            # on 2026-10-26 for the release-file model (#733): step 10's rename and
                            # step 22's open section are gone. They are unexecuted until the v3.8.0
                            # cut.
verified_by: brookstalley
---

# Cut and publish a Prawduct plugin release

## When to use this

You're ready to publish what's on `develop` to everyone running the plugin.
Confirm you're actually in that situation before step 1:

```
git fetch origin
```

**Is there anything to cut?** Ask this at the level of *scopes*, not the tree.
Substitute the version you intend to cut if you already know it; the literal
placeholder works here, because at this point you are reading the scope list and
not grading a plan:

```
./plugin/bin/prawduct-hook check-releasability --release vX.Y.Z
```

**Read the scope list, not the exit code.** Two outcomes matter — plus one that gives you no
scope list to read at all:

- **A record refusal on stderr, exit 1, and NO scope list** — `bad-change-fragment:`,
  `scope-in-both-shapes:`, `bad-change-log-tag:` or `unclassifiable-pending-entry:`. The gate
  refused the pending record itself before it could be trusted, so there is nothing to read here
  yet. **Fix what it names and re-run**; the
  reason-code table in Phase 0 step 0 says how. Do not read this as either outcome below — the
  absence of a scope list is the tell.

- **It names one or more release-pending scopes** — one per fragment in `.prawduct/changes/`,
  where each branch records its change as `<scope>.md`. That set is the unreleased content.
  **Proceed.**
  At this point there is normally no release plan yet, so expect
  `no-release-plan: … N scope(s) are release-pending …` on **stderr with exit 1**.
  *That is the correct result here* — you have not written the plan yet, and
  writing it is Phase 0's job. Do not read this exit 1 as "nothing to cut."
- **`releasable: no release-pending scopes — nothing to classify`** on stdout,
  **exit 0** — the last release is out. There is nothing to cut. **Stop.**

If you are **re-entering** this runbook after Phase 0 already sent you to write
the plan, you'll get `releasable: vX.Y.Z — N release-pending scope(s) …` or
`not-releasable: …` instead. Both still name the scope list, so both mean
"there is something to cut" — read them the same way and carry on to Phase 0,
which is where those two verdicts actually differ. (A Phase 0 re-run with nothing pending prints no suite verdict at all: `release_readiness` asks for it only below the no-pending return, so do not read its absence as a green suite.)

Note the inversion: the *stop* case is the one that exits 0, and the *proceed*
case is the one that exits non-zero. Phase 0 step 0 runs this same command for a
different purpose — to grade a plan that exists by then — and there `no-release-plan:`
genuinely does mean stop and go write it. Same command, two jobs; only here is a
missing plan expected.

> **Do not use `git diff origin/main origin/develop` as this test.** It answers
> "do the trees differ," which stopped being the same question once a promotion
> became a *classified snapshot* rather than a content-identical copy
> (`operational-spec.md` § Direction). After any pruned release `main`'s tree
> differs from `develop`'s **permanently and by design**, so that diff is
> non-empty forever — it is large right now because of v3.1.2 — and it cannot
> distinguish "unreleased work" from "work deliberately withheld." Run it for
> orientation if you like; it is not a decision.

Novelty and fitness are separate questions and both are load-bearing: this
section asks whether there is *anything* to ship, Phase 0 asks whether what
there is, is *fit* to ship. Neither substitutes for the other.

## When NOT to use this

- **If you're merging a feature branch into `develop`:** → use `/prawduct:pr`.
- **If you're about to open a `develop` → `main` PR:** → don't. Phase 2 below
  replaces it. Close any such PR with a note that you promoted directly.

## Before you start

**Blast radius:** every repo with the plugin installed re-resolves `main` at its
next session start and picks this version up on its own. There is no recall —
the only way back is another release.

**Prerequisites** — check every line before step 1:

- [ ] Push access to `origin` for both `develop` and `main`. The promotion
      commits straight to `main`; no PR is involved.
- [ ] You're on `develop` with nothing uncommitted and nothing unpushed:
      `git status -sb` prints `## develop...origin/develop` and no file lines.
- [ ] The new version number, decided. The tag is `vX.Y.Z` (for example,
      `v3.2.0`); the version files carry it without the `v` (`3.2.0`).

      **Ratified norm** — `.prawduct/artifacts/operational-spec.md` `## Direction`
      (2026-07-17), pointer row in `project-preferences.md`:

      > Versioning is conservative: a small feature is a patch bump, not a
      > minor-per-feature.

      That is the whole binding rule. It is a **judgment norm** — no mechanical
      size test, so "small" is your call. A departure in either direction is a
      recorded decision, not a reflex: record it in the release plan.

      > 🚧 **The major and minor tiers are NOT ratified — they are read off
      > release history.** Observed practice: a break in gate semantics or
      > persisted state formats has been a major; a substantial new capability or
      > a subsystem going live has been a minor (v3.1.0; v3.2.0 is planned for the
      > backlog-service go-live). Treat these as precedent, not rule, and ask the
      > maintainer when the call is close. **Do not read the ratified norm as
      > meaning "everything that is not a major is a patch"** — that would erase
      > the minor tier and misnumber the next subsystem release.

---

## Phase 0 — Releasability

*"Is there anything to ship?" is not "is everything **fit** to ship?" The check at the top of this
runbook answers only the first. On v3.1.2 the two diverged, and following Phase 2 literally would
have published the backlog-service subsystem with all four of its go-live blockers open — to every
installed consumer, unrecallably. This phase is the second question (REL-8P6M).*

0. Confirm every release-pending scope is accounted for:

   ```
   ./plugin/bin/prawduct-hook check-releasability --release vX.Y.Z
   ```

   **Expected:** a `scanned:` line naming what the gate looked at — change-log entries, tagged
   entries, change fragments, release-pending records, the scopes they enumerate, and how many
   enumerate none — then
   `releasable: vX.Y.Z — N release-pending scope(s), M shipping, K withheld` and the two lists.
   **Note `K` — it selects the promotion shape at Phase 2.**

   Read the `scanned:` line as the gate's denominator — a verdict is only as good as what it looked
   at. Several entries per scope is ordinary, so the two counts differing is not a signal; the
   number to read is the last one, and it is `0 unclassifiable` on every run that gets this far,
   because a non-zero one refuses instead.

   Beneath it, `digest headline: '…' (.prawduct/release-headline.md → plugin/CHANGELOG.md)` — the
   pending headline's first line, printed back verbatim. The cut puts it directly under this
   release's heading, which makes it the line the version-delta banner shows every repo crossing
   this version, and the whole failure mode is a line nobody looked at. Until Phase 1 step 2 writes
   it, this reads `digest headline: none`. After the cut it reads `digest: vX.Y.Z already cut (…)`:
   the release file exists and there is nothing left to ask. There is no coverage line: the cut
   writes each fragment's own consumer note, and Phase 1 step 2's `none:` review is that check.
   Where the line is absent, the `NOTE:` below says why.

   Last, `suite: green — <which evidence vouched>`. Read what it actually claims: the saved run
   is recorded green and current **as of now**. It is not a statement about the tree you will
   tag — Phase 1 rewrites the digest, the change-log archive and the version files after this
   point, and nothing checkable at Phase 0 can
   vouch for a tree that does not exist yet.

   **Also exit 0, but different:** `releasable: no release-pending scopes — nothing to classify`.
   This line names no version and yields **no `K`**; read it as `K = 0`. Reaching it *during* a
   release contradicts this runbook's own entry condition, so treat it as a symptom, not a pass:
   Phase 1 step 3 already ran (the cut removes the shipping fragments, which empties the pending
   set). An empty pending set here is an honestly empty one: a record the gate cannot classify
   refuses by name before this line is reachable.

   **If not:** it stops, printing either a `not-releasable:` header plus one `ERROR:` line per
   problem, or — when an input it needs is missing outright — a single bare `<reason-code>:` line.
   Find the line you are looking at:

   `unclassified scope(s)`
   - **Add a row** to the `## Release classification` table in
     `.prawduct/artifacts/release-plan-vX.Y.Z.md`, naming `ships` or `withheld` + an **open**
     blocker id. Create the release plan if it does not exist yet.

   `withholding blocker(s) no longer open`
   - The reason to withhold is gone. **Re-take the decision:** either it ships now, or a different
     open blocker withholds it.

   `nothing release-pending behind them`
   - A stale table row. **Delete it.**

   ``scope(s) classified `withheld` whose entries already carry this release's tag``
   - The table withholds a scope that the change-log archive already records as shipping in this
     release, so a cut has already shipped it. **Do NOT delete the row** — that makes the gate pass
     and ships the very scope the table withheld. Decide which is true. If it ships, reclassify the
     row as `ships`. If it is withheld, undo the cut before committing (Phase 1 step 3 says how)
     and re-run it.

   `cannot-verify-blockers:`
   - A withholding blocker's liveness could not be read. On the GitHub Issues backlog it is read
     from the local backlog cache, so the message says whether the cache could not be opened or
     does not hold that id: **run `prawduct-hook backlog sync --repo <owner/repo>` and re-run**
     first. On the markdown backlog an Issues blocker (`#N`, `owner/repo#N`) cannot be read at all.
     If it still refuses, **confirm each withholding blocker is open by hand**
     and record that confirmation in the release plan beside the classification table. Then proceed
     — the gate stays red by design and the recorded hand check is what replaces it. **Blocker
     liveness is the only thing it withholds**: every other check still ran, so fix any other
     `ERROR:` line printed beside this one before proceeding.

   `unreadable-project-state:`
   - The gate cannot tell which backlog is live, so it cannot judge blocker liveness either.
     **Fix or restore `.prawduct/project-state.yaml`**, then re-run. (This is not the cutover case —
     the message says so precisely because the two need different remedies.)

   `bad-change-fragment:`
   - A fragment in `.prawduct/changes/` that fails validation, as
     `bad-change-fragment: <file>: <code>: <detail>`, one line per problem. A file that cannot be
     validated makes the pending set untrustworthy, so the gate gives no verdict. **This is not a
     gate defect — fix the fragment** as the detail says (`plugin/templates/change-fragment.md`
     documents every key), then re-run.

   `scope-in-both-shapes:`
   - One scope is pending as a fragment and as a legacy change-log entry, so its record is in two
     places. **Keep one:** fold the entry's text into the fragment and delete the entry.

   > **The two rows below refuse legacy change-log entries.** This repo records pending work as
   > fragments, so a pending entry in `.prawduct/change-log.md` is itself the fault. Fix what the
   > row names. If the entry is release-pending, then convert it with
   > `./plugin/bin/prawduct-hook migrate-change-log` (a preview; add `--apply` to write it).

   `unclassifiable-pending-entry:`
   - A release-pending change-log entry carrying no `scope=`. It is in no scope, so it reaches no
     row of the classification table, so it can be neither shipped nor withheld — the gate would be
     certifying a release over work it never enumerated. **This is not a gate defect — add a
     `scope=` to each entry it names** (the message gives the title and the change-log line number),
     matching the `scope:` of the build plan the work belongs to. Then re-run.

   `bad-change-log-tag:`
   - A change-log tag line the gate refuses to act on. **This is not a gate defect — fix the tag.**
     The common case is a `release=` value that is not a version (`release=unreleased`,
     `release=TBD`): *any* `release=` value marks the entry already-released, so its whole scope
     drops out of the pending set and the gate would otherwise answer "nothing to cut" while the
     work never ships. That is not hypothetical — it hid an entire branch from v3.2.8.
     **Release-pending is statusless with NO `release=` tag: delete the tag** — unless the entry did
     ship, in which case set `release=` to the version it shipped in. The other case is one
     entry carrying several `prawduct:` tag lines that disagree — merge them and resolve the
     conflict. The message names the entry and its line number.

   `WARNING: … has no build-plan file` · `WARNING: duplicate scope=`
   - **Advisory, not a stop.** The first says work is shipping with no plan describing it (worth a
     look, not worth blocking a release); the second says two plans declare one scope, so
     scope→plan resolution is decided by sort order. Neither changes the exit code.

   `WARNING: … .prawduct/release-headline.md is absent` · `… is empty` · `… starts with a heading`
   · `… cannot be read`
   - **Advisory, not a stop**. "Absent" fires on a correct release, once: **Phase 1 step 2 writes
     the file**, and this warning is that step arriving early, while you are still reading Phase 0
     output and the headline is cheap to write. It is not a refusal because Phase 0 runs *before*
     the step that fixes it; the cut itself refuses `no-headline` without it. A headline that
     starts with a heading would give the banner nothing to show. Both failures have shipped:
     v2.1.6 was tagged with no headline at all, and v3.4.0 went out leading with a placeholder.

   `WARNING: plugin/CHANGELOG.md already has a section for vX.Y.Z`
   - The cut writes the release's section itself and refuses `release-in-changelog` while one
     exists, so a section written by hand (or one left by the procedure before v3.8.0) is reported
     here first. **Remove it, or move its first paragraph into `.prawduct/release-headline.md` if
     it was the headline.**

   `NOTE: … the declared consumer digest, cannot be read / is not a file` · `NOTE: no --release
   given` · `NOTE: vX.Y.Z is already cut`
   - The first two mean a check did not run: fix the file (the cut refuses `digest-unreadable` or
     `digest-missing` until you do), or pass `--release`. The third is the ordinary state after
     Phase 1 step 3: the release file exists, so both digest checks step aside rather than ask
     about a section the cut wrote. A `WARNING: consumer_digest: …; the consumer digest checks did
     not run` means `.prawduct/project-state.yaml`'s declaration is invalid or unreadable: fix
     what it names.

   `unproven-suite:`
   - Nothing has said this code passes. Four states reach this one line and the message names
     which: no `.test-evidence.json` at all, a saved run reporting failures, a run that predates
     this session and can no longer be matched to the tree, and a run that reported itself
     `degraded` (a contended run covers less than its counts imply, so a release must read it as
     "no run" rather than "a green run"). **Run the suite and record it** —
     `prawduct-hook test-evidence record` — then re-run. This is not a gate defect and there is no
     variant of it to work around: v2.1.6 shipped on a red suite because the release path read no
     test result at all.
   - **Read the bound.** It asks the same question `prawduct-hook test-status` asks, so a repo
     cannot be green for the builder and stale for the release. That question is *"is the saved
     run green and current"*, **not** *"did a run meet the tree you are about to tag"* — Phase 1
     rewrites `plugin/CHANGELOG.md`, the change-log archive, `.prawduct/changes/`,
     `plugin/VERSION`, `plugin/.claude-plugin/plugin.json` and `pyproject.toml` after this phase,
     so the tagged tree does not exist yet. If you want a
     green-suite check at the tagging moment, that is a control at Phase 2, not this one.

   `no-release-plan:` · `no-change-log:` · `no-version:` · `unreadable-release-plan:` · `no-backlog:`
   - An input the gate needs is missing or unreadable. **The message names the path** — create or
     fix it, then re-run. (`no-version:` means neither `--release` nor `plugin/VERSION` resolved;
     `--release` is authoritative and always worth passing explicitly, since Phase 1 step 7 bumps
     `VERSION` *after* this phase runs.)

   - Anything else → stop. The `ERROR:` line names its own fix; if it does not, that is a defect in
     the gate, not in you.

   The table is a partition, not a checklist: every release-pending scope appears **exactly once**,
   and nothing appears that is not release-pending. That exactness is the point — a subset would
   satisfy "everything I listed is real" while still letting an unlisted scope ship unexamined,
   which is the v3.1.2 shape.

   > **A deferred *issue* is not a withheld *scope*, and the table has room only for the second.**
   > `withheld` means: this work is **built and sitting on `develop`**, and it must not reach `main`.
   > An open issue you decided not to build this cycle has no fragment, so it has nothing
   > release-pending behind it — put it in the release plan's **prose**, where the reasoning belongs,
   > and never in this table. A row for one lands as `nothing release-pending behind them` and stops
   > the release.
   >
   > This matters twice, because `K withheld` also chooses the promotion path at Phase 2. Counting
   > deferred issues inflates it and routes a perfectly ordinary release to
   > `promote-a-pruned-release.md`, whose whole reason for existing — a `main` tree deliberately
   > unlike `develop`'s — does not apply. **Take `K` from the gate's own output, never from the
   > release plan's narrative.** *(Written after the v3.3.4 plan's first draft carried six such rows
   > and read `K = 6`. Both errors, one confusion: "six things aren't shipping" is true in English
   > and false in this table's vocabulary.)*

   ```markdown
   ## Release classification

   | Scope | Disposition | Blocker |
   |---|---|---|
   | coverage-perf | ships | |
   | v3.2.0-golive | withheld | BKL-6J2X |
   | backlog-sync | withheld | #1024 |
   ```

   A blocker is a markdown id (`BKL-6J2X`) or an Issues id (`#1024`, `owner/repo#1024`).

---

## Phase 1 — Release prep on `develop`

1. Preview the cut:

   ```
   ./plugin/bin/prawduct-hook cut-change-log --release vX.Y.Z
   ```

   **Expected:** exit 0 and `cut-change-log (dry-run): N fragment(s) ship in vX.Y.Z: <scopes>`,
   then `archive: YYYY-MM.md` naming the month buckets the entries will join,
   `consumer notes: N to be written to plugin/CHANGELOG.md as a new section at line L (release
   file .prawduct/releases/vX.Y.Z.md)`, one `none: <scope> — <reason>` line per fragment that gives
   consumers nothing, `kept pending (withheld): …` on a pruned release, then the section itself
   between `--- section (as written to .prawduct/releases/vX.Y.Z.md) ---` and `--- end ---`, and
   `Re-run with --apply to write. Nothing was written.` That block is exactly what step 3 writes
   and what step 20 publishes; read it as the release notes.

   The cut reads the same pending set and the same `## Release classification` table Phase 0
   step 0 graded: every file in `.prawduct/changes/` is release-pending, a `ships` row is cut and
   a `withheld` row is kept. **Do not pass `--scope` here.** It names the scopes to cut directly,
   bypassing the table, which is the one check that keeps withheld work out of this release.

   **If it prints `nothing to do`:** no fragment is pending, so nothing ships and there is no
   release to cut. Go back to the check at the top of this runbook.

   **If it refuses** — `refused: <code>: …. Nothing was written.`, exit 1:

   `unclassified-fragment:` · `no-release-plan:` · `bad-release-plan:`
   - The table does not classify every pending fragment, does not exist, or does not parse. Phase
     0 step 0 refuses the same states, so you skipped or changed something after it. **Fix the
     release plan and re-run Phase 0 step 0**, then this step.

   `invalid-pending-set:`
   - A fragment fails validation, or one scope is pending both as a fragment and as a legacy
     change-log entry. Phase 0 step 0 names each one by file and code (`bad-change-fragment:`,
     `scope-in-both-shapes:`); its remedy rows say how to fix them.

   `no-headline:`
   - `.prawduct/release-headline.md` is absent, empty or unreadable, and prawduct's declaration
     (`consumer_digest:` in `.prawduct/project-state.yaml`) requires a headline. **Do step 2
     first**, then re-run this step.

   `release-in-changelog:`
   - `plugin/CHANGELOG.md` already has a section naming vX.Y.Z (the message gives its line). The cut
     writes that section itself, as a new section, so one already there would be published twice or
     edited. **Remove it, or move its first paragraph into `.prawduct/release-headline.md` if it was
     the headline**, then re-run.

   `release-already-cut:`
   - `.prawduct/releases/vX.Y.Z.md` exists, so this release is cut, and a fragment it does not hold
     is pending. That fragment belongs to the next release. **Classify it `withheld`** (or leave it
     for the next cut), then re-run.

   `digest-declaration-invalid:` · `digest-missing:` · `digest-unreadable:` · `marker-missing:` ·
   `releases-ignored:`
   - The declaration, the changelog it names, or the release directory is not usable: an invalid
     or unreadable `consumer_digest:` block, a declared changelog that is not a file or not UTF-8,
     a declared marker line not in it, or git ignoring `.prawduct/releases/`. **Fix what the message
     names**, then re-run.

   `archive-ignored:`
   - git would ignore `.prawduct/change-log-archive/`, so the commit would carry the fragments'
     removal and none of the history they move to. **Un-ignore the archive directory**, then
     re-run.

   `bad-version:` · `no-change-log:`
   - `--release` is not a version like `v3.7.2`, or the change log is unreadable and there is no
     fragment directory. **Fix what it names**, then re-run.

2. **Read every `none:` line from step 1, then write the headline.** A `none:` reason is the
   fragment author's claim that consumers need not hear about this change, and the cut publishes
   nothing for it. For each one, decide whether the reason is true. If a consumer does need to
   know, replace the `none:` line in that fragment's `## Consumer note` with the note, then re-run
   step 1. Fragments that `migrate-change-log` converted from the legacy log say so in their
   reason; those were never decided by anyone.

   Then write this release's headline into `.prawduct/release-headline.md`. Write it from step 1's
   shipping list and its notes, as **one long unwrapped line**. The cut puts it directly under the
   release's heading, then removes the file.

   **Expected:** `./plugin/bin/prawduct-hook check-releasability --release vX.Y.Z` prints your line
   back as `digest headline: '…' (.prawduct/release-headline.md → plugin/CHANGELOG.md)`, with no
   headline warning, and step 1's preview shows it under `## vX.Y.Z`.

   > *Why the headline comes before the cut: the cut writes the release's section once, from this
   > file, and refuses `no-headline` without it. A headline added afterwards would be an edit to a
   > section already written, and the version-delta banner shows that line to every repo crossing
   > this version.*

   > *Why one unwrapped line: the banner reads the first physical line, so a bold lead-in wrapped
   > across two ships an unpaired `**` (the v3.5.0 defect step 11a records).*

3. Apply the cut:

   ```
   ./plugin/bin/prawduct-hook cut-change-log --release vX.Y.Z --apply
   ```

   **Expected:** step 1's summary again, with `written` where the preview said `to be written`,
   ending `removed N fragment(s); commit the archive, release file, changelog and removals
   together.`

   It renders each shipping fragment into its month bucket under `.prawduct/change-log-archive/`
   as an entry tagged `release=vX.Y.Z`, writes the release's section to
   `.prawduct/releases/vX.Y.Z.md`, inserts that section into `plugin/CHANGELOG.md` above the newest
   release, and removes the shipping fragments and `.prawduct/release-headline.md`. Withheld
   fragments are not touched, so they stay pending for the next release.

   **If it prints `refused: write-failed:`:** every file was restored. Fix the cause it names and
   re-run.
   **If it prints `refused: removal-failed:`:** the archive, release file and changelog are
   written, and some fragments (or the headline file) are still on disk. Re-run the same command.
   The release file exists, so it writes nothing and removes what the archive and the release
   already hold.

   > *Nothing here is pushed or committed yet. To undo the whole cut before step 12, restore
   > `.prawduct/change-log-archive/`, `.prawduct/changes/`, `.prawduct/release-headline.md` and
   > `plugin/CHANGELOG.md` from `HEAD`, and delete `.prawduct/releases/vX.Y.Z.md`. The release
   > file must go too: while it exists, the cut treats vX.Y.Z as already cut.*

4. Confirm the pending set shrank to exactly what you withheld:

   ```
   ls .prawduct/changes/
   ./plugin/bin/prawduct-hook check-releasability --release vX.Y.Z
   ```

   **Expected:** `ls` lists exactly the `withheld` rows' `<scope>.md` files, and nothing on an
   unpruned release (`ls -a` still shows `.gitkeep`, which keeps the directory, and with it the
   fragment rules, in every clone). The gate agrees. On an unpruned release
   it prints `releasable: no release-pending scopes — nothing to classify (…, N scope(s) already
   tagged release=vX.Y.Z)` and exits 0. On a pruned one it names only the withheld scopes.

   **If a `withheld` scope is missing from the directory:** the cut shipped it. The gate says so
   too: ``scope(s) classified `withheld` whose entries already carry this release's tag``. Undo
   the cut (the note at the end of step 3), then fix the release plan or the fragment before you
   run step 1 again.

   The gate also prints advisories that do not change its exit code. Phase 0 step 0 names and
   answers each one, so read them there.

5. Confirm the cut's writes are the whole change:

   ```
   git status --short .prawduct/change-log-archive .prawduct/changes .prawduct/releases .prawduct/release-headline.md plugin/CHANGELOG.md
   ```

   **Expected:** one `M` (or `??` for a month with no file yet) per bucket step 1 named under
   `archive:`, `?? .prawduct/releases/vX.Y.Z.md`, ` M plugin/CHANGELOG.md`,
   ` D .prawduct/release-headline.md`, and one ` D .prawduct/changes/<scope>.md` per shipping
   fragment. Nothing else.

6. Confirm each shipping scope's build plan is actually closed out:

   ```
   ./plugin/bin/prawduct-hook plan status <each shipping scope's plan>
   ```

   **Expected:** every chunk `done` or `dropped`, **except a chunk whose own acceptance is this
   release**, which cannot be done here by construction. A plan carrying a "Phases 0–3 complete"
   chunk is open *because* you are at Phase 1; that is the one open chunk this step expects, and its
   review lands after Phase 3. Record which plan it is, so the next reader can tell it from a real
   miss.

   **If not:** an open chunk at release means no review certified it. Chunk state is derived from
   review facts, never hand-edited, and only a session with the work in context can say whether the
   chunk is finished. Ask the chunk's author, or ship knowing the plan says the work is incomplete.
   (Until #1072 is fixed, a `final` review run mid-plan can certify later chunks it never reviewed,
   so `done` is weaker evidence than it reads: check the certifying review's chunk set when a
   result looks too clean.)

7. In `plugin/VERSION`, replace the old number with the new one, without the `v` — `3.2.0`
   for a `v3.2.0` release.

8. In `plugin/.claude-plugin/plugin.json`, replace `"version"` with the same
   number.

   > *Why: that string is the update cache key. A release that forgets it does
   > not ship, however clean the push.*

9. In `pyproject.toml`, replace `version = "3.0.3"` with the same number.

   > *Adjudicated, not derived: the file's own comment asks for this bump;
   > `documentation/release-process.md` step 2 didn't name it until v3.1.1.*

10. **On a minor or major bump — not a patch — refresh `README.md`'s `## Recent Changes`** so the
    current line is represented there. (`plugin/CHANGELOG.md` needs nothing here: step 3 wrote its
    `## vX.Y.Z` section, and `develop` carries no open `-dev` section to rename.) If the README
    already has a section for this line under a prerelease heading, bring that one up to date
    rather than adding a second. Rewrite the section; do not append a
    per-release bullet. A patch has nothing to say on that surface, so skipping it is the correct
    outcome and not an omission.

    > *Why it is conditional, and why it lives here: the README is the first thing a
    > prospective user reads, and no release had ever updated it — it sat two minor
    > versions and eight releases stale (3.1.0 through 3.2.4) because no release document
    > named the file. A per-release step would no-op on every patch, and a step that
    > usually does nothing is a step you stop reading. A minor-bump-only step fires rarely
    > and has something to say every time it does. `documentation/release-process.md` step 5
    > points here for both files rather than restating them, so deleting this paragraph is
    > what makes that pointer dangle.*

11. **Clear the pointer if one is still set, then archive the plans this release shipped.**
    On gitflow the closing PR deliberately RETAINS each plan — the work is not released yet
    — so this is where that retention ends. A pointer aimed at a plan that declares
    `branch:` is inert (that plan governs only its own branch, which is gone), so clearing it
    is tidiness; only a pointer-resolved plan's pointer actually governs, and it is cleared
    here. `/prawduct:pr`’s Merge Flow *"Confirm the bookkeeping merged WITH the PR"* step
    owns that split. Archiving is what ends retention in
    both cases. Skip it and the live artifacts directory re-accumulates the pile the
    archive exists to prevent.

    First set `active_build_plan:` to `null` in `.prawduct/project-state.yaml`.

    > *Why this order, and it is the whole reason the step reads this way: the sweep
    > **refuses** to archive the plan the pointer names — archiving it would leave the
    > pointer at a moved file, which every gate reads as "no active build plan" and goes
    > quiet rather than failing. So a pointer left set is a plan left live. Clear first and
    > it is swept with the rest; clear after and you have to come back for it.*

    Then sweep. Step 3's cut wrote each shipped scope into the change-log archive tagged
    `release=vX.Y.Z`, which is the mechanical answer, so this picks nothing by hand:

    ```
    prawduct-hook plan-backfill            # preview: names each plan and its release
    prawduct-hook plan-backfill --apply    # one confirmation covers the whole set
    prawduct-hook archive-change-log --apply   # bound the live change log (no-op under its threshold)
    ```

    **Expected:** exit 0, and every plan whose scope step 3 shipped moves into `archive/`,
    stamped `lifecycle: completed` and `released_in:`. It is a **no-op for anything still
    pending** — a withheld fragment never reached the archive — so this cannot archive
    withheld work on a pruned release.

    **If `--apply` exits 1:** it archived what it could and one or more plans the change
    log says shipped did **not** move. Nothing is half-done, and this is not a failed
    release step — but do not proceed on the strength of "it printed a list".

    Look in **two** places: plans it declined before trying are on stdout under
    `NOT moving`; a plan that failed at write time prints to **stderr** as
    `could not archive <scope>: …` and appears under neither heading.

    > ⚠️ **Do not reach for `archive-plan` here, and do not loop on "re-run until 0".**
    > `archive-plan` asks the *same* refusal predicate for most of these, so it declines them
    > for the same reason the sweep did. **Each reason names its own remedy, and they are
    > all different:** *"already exists"* → rename one of the two, then re-run.
    > *"already records lifecycle …"* → the plan already has an end of life and only needs
    > moving; `git mv` it into `archive/` and it leaves the live scan. *"cannot read …"* →
    > fix the file's encoding by hand first; nothing can converge a plan it cannot decode.

    > *"…N of M chunks not done (Chunk …)"* → **the one reason `archive-plan` does NOT
    > share** (v3.3.1, #634). The sweep cannot tell a dead plan from live work whose scope
    > shipped partially, so it hands you the call. If the chunks shipped, a review must certify
    > them: chunk state is derived from review facts and is never hand-edited. If the work
    > stopped, run `archive-plan <path> --state superseded --superseded-by "…"`.

    Once each named plan has had its own remedy, re-run and expect exit 0 — **except where a
    completeness refusal was answered with an explicit `archive-plan`**, which removes the plan
    from the live set directly, so the re-run has nothing left to move and reports it under
    neither heading. A preview always exits 0 even when it lists refusals, because it
    attempted nothing.

    > ⚠️ **Read the `NOT moving` list before `--apply`.** The preview separates plans it
    > will archive from plans the change log says shipped but which it refuses (a name
    > already in the archive, a plan already carrying a terminal state, one it cannot
    > read). Those need a person, and they are the ones that quietly stay live otherwise.

    A plan whose work was **descoped** rather than shipped has no archived entry for this
    release, because no fragment of its scope was cut, and is not swept. Give it its end of life by hand, naming what replaced it:
    `prawduct-hook archive-plan <path> --state superseded --superseded-by "<what/why>"`.

11a. **Stage everything, then run the suite again.** Steps 1–11 rewrote the digest, the archive
    and the version files, removed the shipped fragments and moved a pile of plans; Phase 0's `unproven-suite:` gate graded the tree that existed *before* all of
    that, and says so. This is the only control that reads the tree you are about to tag.

    ```
    git add -A
    prawduct-hook test-evidence record
    ```

    **Expected:** exit 0, `recorded: N passed, 0 failed`.

    **`git add -A` first is load-bearing, not tidiness.** Several suite checks enumerate the repo
    through `git ls-files`, so step 11's archive moves are invisible to them until they are staged
    — the walk then opens live-directory paths that are no longer there and the suite dies on
    `FileNotFoundError` rather than on anything real.

    > *Both failure modes below were measured at the v3.5.0 cut, on a suite that had been green
    > forty minutes earlier at Phase 0. Neither is bookkeeping.*
    >
    > 1. **A wrapped CHANGELOG headline.** The banner reads the section's first physical **line**,
    >    so a bold lead-in wrapped across two lines ships an unpaired `**` on the single most-read
    >    line prawduct emits — the exact defect `silent-clear-checks` fixed one release earlier,
    >    reintroduced by a headline written at the file's ordinary wrap width. **Step 2 writes the
    >    headline as one long unwrapped line**, the way every shipped section does.
    > 2. **Unstaged archive moves**, as above.
    >
    > *If it is red:* fix it here. Everything up to the Checkpoint is undone by an ordinary commit
    > on `develop`, and a red tree is far cheaper now than after step 19.


12. Commit the prep:

    ```
    git commit -am "release: prep vX.Y.Z"
    ```

    **Expected:** `[develop <sha>] release: prep v3.2.0`, and the summary lists the archive
    bucket(s), `plugin/CHANGELOG.md`, a `create mode` line for `.prawduct/releases/vX.Y.Z.md`, and a
    `delete mode` line per shipped fragment and for `.prawduct/release-headline.md`. They go in one
    commit: the fragments' removal without the archive drops the record, the archive without the
    removal leaves the scopes pending for the next release too, and the release file is what tells
    a re-run the release is cut.

    > *`commit -am` stages modifications and deletions but not the new release file. Stage it
    > first: `git add .prawduct/releases/vX.Y.Z.md`.*

13. Push it:

    ```
    git push origin develop
    ```

    **Expected:** a line ending `develop -> develop`.

    > *Why: Phase 2 builds `main` from `origin/develop`. Anything still local
    > won't be in the release.*

### Checkpoint

`origin/develop` now holds the whole release: bumped version, the shipped scopes in the
change-log archive tagged `release=vX.Y.Z` with their fragments removed, cleared plan
pointer — and, on a minor or major bump, a `## Recent Changes` section that covers this line. Everything up to here
is undone by an ordinary commit on `develop`, so this is a safe place to stop
and come back.

> ⚠️ **Safe for consumers; not free for you.** Step 8 just published the update *cache
> key*. Claude Code caches the plugin under `plugins/cache/prawduct/prawduct/<version>/`
> and keys it on that string alone. A `ref: main` install cannot see the new key yet, so
> consumers are unaffected. But a marketplace whose `source` is `directory:` — **your own
> machine** — resolves whichever branch is checked out, so it can cache the *prep* tree
> under the release's key. The key does not change when Phase 2 lands the real tree, so
> that install never refreshes, and the longer you sit here the longer you are testing a
> plugin that is not the one shipping. `Done when` catches it.

---

## Phase 2 — Promote `develop` to `main`

**Two promotion shapes exist, and step 0 already told you which one you are in.** Read `K withheld`
from its output and take exactly one branch:

**IF `K withheld` is 0**, or step 0 printed `no release-pending scopes — nothing to classify` (which
names no `K`, and means the same thing here) — everything on `develop` ships, so `main`'s tree
becomes `develop`'s:
- Continue with step 14 below.

**IF `K withheld` is 1 or more**, or step 0 refused with `cannot-verify-blockers:` and you recorded
the by-hand blocker check — `main`'s tree is a deliberately chosen subset of `develop`'s:
- **Stop here.** Go to `.prawduct/runbooks/promote-a-pruned-release.md`, which replaces steps 14–21
  and carries its own `Done when`.
- Do **not** run step 14. `git read-tree --reset -u origin/develop` at step 15 would publish the
  withheld work — that is the whole failure Phase 0 exists to prevent, arriving one phase later.

14. Switch to the release surface and bring it up to date:

    ```
    git checkout main && git pull
    ```

    **Expected — both:**
    - `Switched to branch 'main'` (or `Already on 'main'`)
    - then `Already up to date.`, or a fast-forward summary

    > *Chained on purpose: if the checkout fails, the pull must not run.*

> ⚠️ **`git read-tree --reset -u` overwrites `main`'s index and working tree in
> place.** Anything uncommitted on `main` is gone.

15. Set `main`'s tree to `develop`'s:

    ```
    git read-tree --reset -u origin/develop
    ```

    **Expected:** no output.

16. Commit it on `main`, using the headline you wrote at step 2:

    ```
    git commit -m "release: vX.Y.Z — <headline>"
    ```

    **Expected:** `[main <sha>] release: v3.2.0 — <headline>`.

17. Confirm `main` is content-identical to `develop`:

    ```
    git diff --stat origin/develop HEAD
    ```

    **Expected:** no output.
    **If not:** any output at all means the tree-set didn't take → go to step 15.

18. Confirm the commit actually carries the bump:

    ```
    git show HEAD:plugin/VERSION
    ```

    **Expected:** the new number, `3.2.0` — not `3.1.0`.
    **If not:** the bump never reached `develop`. Discard this commit with
    `git reset --hard origin/main`, fix it at step 7, then come back to step 14.

> ⚠️ **IRREVERSIBLE — step 19 publishes to every installed consumer.**
> **Proceed only if:** step 17 printed nothing and step 18 printed the new
> number.
> **Abort if:** either one disagrees, or you aren't sure → stop. Nothing on
> `origin/main` has moved yet; aborting costs only the time to redo Phase 2.
> **Recovery after this point:** none — repos that have already re-resolved
> `main` keep what they got. Recovery is forward-only: fix on `develop`, bump
> the version again, and run this runbook again.

19. Publish:

    ```
    git push origin main
    ```

    **Expected:** a line ending `main -> main`.

20. Publish the GitHub Release, using the release's whole section from its release file as the
    notes. **This step is also what creates the tag** — do not tag separately first:

    ```
    tail -n +3 .prawduct/releases/vX.Y.Z.md > /tmp/notes-vX.Y.Z.md   # the section without its heading
    gh release create vX.Y.Z --target "$(git rev-parse main)" \
      --title vX.Y.Z --notes-file /tmp/notes-vX.Y.Z.md
    ```

    **Expected:** one line — the release URL, ending `/releases/tag/vX.Y.Z`.
    **If the notes look wrong:** `.prawduct/releases/vX.Y.Z.md` is the section the cut wrote and
    step 1 previewed, so fix the notes there and in `plugin/CHANGELOG.md` alike, then re-run with
    `gh release edit` rather than `create`.
    **If it reports the tag already exists:** something tagged ahead of this step. Confirm
    `git rev-parse vX.Y.Z` is the commit you just pushed, then re-run without `--target`
    to attach the Release to the tag that is already there.

    > *Why the Release creates the tag, rather than `git tag && git push` as a step
    > before it: `verify-release.yml` fires on the tag push, and one of the three things
    > it checks is whether a Release exists. Tag first and the job is dispatched **before
    > the fact it checks becomes true**, so it goes green only if you publish faster than
    > a runner boots. At v3.2.4 that margin was **9 seconds** and the only thing defending
    > it was typing speed — a pause here to read output would have turned a correct
    > release red. Creating both in one call means no instant exists at which the tag is
    > there without its Release — **and that, not the absence of a trigger, is what makes the
    > race unlosable.** The tag-push run does fire on this path (measured at v3.2.5; see step
    > 21), it simply cannot catch the tag Release-less. It also sharpens what a **red** tag-push
    > run means: not this path, which is green by construction, but a tag that arrived by some
    > other route — exactly the case worth a red build.*

    > *Why the whole section, not just the headline: `plugin/CHANGELOG.md` ships **inside**
    > the plugin, so it is unreadable to anyone who has not installed it. The Releases page
    > is the only public copy. A pushed tag alone lands on `/tags` and nowhere else, leaving
    > `/releases` reading "no releases published" — which is both where a consumer whose
    > banner just announced an update goes to find out what changed, and the first thing
    > someone evaluating prawduct sees.*

21. Bring the tag back locally, and run the same check in CI:

    ```
    git fetch origin --tags
    ./plugin/bin/prawduct-hook check-released vX.Y.Z
    gh workflow run verify-release.yml -f tag=vX.Y.Z
    ```

    **Expected:** the tag arrives in the fetch output, then
    `released: vX.Y.Z — 3 of 3 verified`, then silence from the dispatch. Give the run
    ~30s and read it — this is a `Done when` item below, not fire-and-forget:

    ```
    gh run list --workflow verify-release.yml --event workflow_dispatch --limit 1 \
      --json databaseId,status,conclusion,createdAt
    ```

    **Expected:** `"conclusion":"success"`, with a `createdAt` from the last few minutes.
    **If `createdAt` is old:** your dispatch has not registered yet and this is a *previous*
    dispatch — wait and re-run. Do not grade the release on it.

    > *Why `--event workflow_dispatch` rather than the newest run of any kind: it names the run
    > you just asked for. A tag-push run **will** be sitting beside it — see below — and it is a
    > different run, so "newest" would let the two trade places. This filter is not a nicety;
    > it is what makes the query deterministic.*

    > *Why the fetch: step 20 created the tag on the remote, so your clone does not have
    > it yet and every local command naming `vX.Y.Z` — including `check-released` and the
    > install-sha check in `Done when` — would fail on an unknown ref.*

    > *Why the CI run is dispatched by hand here rather than relied on to arrive: **expect
    > two runs, and dispatch anyway.** A tag created through the Releases API **does** emit a
    > `push` event — measured at v3.2.5, run `31049244616`, `headBranch: v3.2.5`, `--event push`,
    > green, firing on its own beside the hand-dispatched `31049256434`. The dispatch stays because
    > it names a run you asked for at a time you know, which is what the `--event workflow_dispatch`
    > query above depends on; the arriving run is a bonus, not the check. Two green runs is the
    > normal shape of this step.*
    >
    > *This corrects a prediction that stood here until v3.2.5 and was **wrong**: that a
    > Releases-API tag emits `create` and `release` but not `push`, so the tag-push trigger
    > would not fire on this path. It fires. The note was labelled UNVERIFIED and asked to be
    > measured at the next release, which is how it got caught — reasoned from GitHub's event
    > model and never given a number, the same shape `learnings.md` records against v3.2.4's
    > release plan.*
    >
    > *Step 20's design survives its own warrant being wrong, for a better reason than the one
    > originally written down. The race is not avoided by removing the trigger — the trigger is
    > there. It is avoided because **one call leaves no instant at which the tag exists without
    > its Release**, so the push-triggered job cannot observe the absence it would go red on.
    > v3.2.4 won that race by ~9 seconds of typing speed; v3.2.5 could not have lost it.*

    > *Anyone dogfooding the develop track is, at this instant, running the released plugin
    > without knowing it: the promotion left `develop` carrying the string `main` now uses,
    > so the version-keyed cache resolves the released entry
    > (`documentation/release-process.md` § Dogfooding the develop track). Phase 3 is what
    > ends that window, which is why it is unconditional and immediately next — there is no
    > "nobody is on the track today" branch to take.*

---

## Phase 3 — Reopen `develop`

22. On `develop`, bump the three version files (`plugin/VERSION`,
    `plugin/.claude-plugin/plugin.json`, `pyproject.toml`) to the next **patch** plus a
    `-dev` suffix — after cutting `v3.4.0`, write `3.4.1-dev` — plus, in the same commit, a
    `.prawduct/changes/release-vX.Y.Z.md` fragment recording the cut (copy
    `plugin/templates/change-fragment.md`; `type: chore`, and a `none:` consumer note, because
    release mechanics tell consumers nothing).

    > **Guess LOW, and it is not a style preference — a high guess breaks the banner for
    > the audience this whole step exists to serve.** Version ordering puts a prerelease
    > just below its own release, so `3.4.1-dev` precedes both `3.4.1` and `3.5.0`: from a
    > low guess, *every* possible next cut is a forward move. From a high one it is not —
    > a develop consumer sitting on `3.5.0-dev` that meets a patch cut `3.4.1` moves
    > **backwards**, and `highlights_in_range` and `new_gates_in_range` are both empty on a
    > downgrade, so they get a version move with no release notes and no gate announcement.
    > This also *is* the ratified conservative-versioning norm (`operational-spec.md`
    > § Direction: a minor bump is a recorded decision, not a reflex) — a procedure that
    > defaults to a minor writes the reflex into the runbook. If the next release is
    > already decided to be a minor or major, that decision is what licenses the higher
    > number; record it, don't assume it.

    > **Do not open a `## vX.Y.Z-dev` section in `plugin/CHANGELOG.md`.** The next cut writes
    > that release's section itself, so a `-dev` section would ship in the released changelog
    > beside it, and `test_changelog_matches_the_current_version` fails on a prerelease that has
    > one. Pending
    > notes live in each change fragment and the next headline in `.prawduct/release-headline.md`,
    > written at the next cut's Phase 1 step 2.

    > *Why develop never reads as the released version: the verdict cache keys on the
    > plugin version (`verdict_cache._key`), so a prerelease codebase reporting the
    > released number can replay `covered` verdicts across a judgeability change; and a
    > test consumer pinned to the `develop` ref can only tell which plugin it is running
    > if the banner says so. `-dev` and `-dev.N` are the only suffixes
    > `test_version_is_semver` permits.*

    > **What keeps the suffix out of a cut is step 7, and nothing else.** Step 7 overwrites all
    > three files with the bare release number; that is the only *preventive* control.
    > `check_version_files` runs `git show <tag>:…`, i.e. against a tag that already exists, so
    > it is a post-publish detector — it tells you a `-dev` suffix shipped, it cannot stop it.
    > Nothing on the pre-tag path reads the version files at all (`check-releasability` never
    > opens `plugin/VERSION`). Treat step 7 as load-bearing rather than as one of two belts.

    If the number guessed here turns out wrong at the next cut, **steps 7–9** overwrite all
    three files — the suffix is identity, not a commitment. That covers the *files*; it does
    not un-tell a consumer that already crossed onto the marker, which is the other reason
    the guess goes low rather than high.

---

## Done when

*These are the **whole-develop** tests. A pruned promotion left this document at Phase 2 and has its
own `Done when`: the content-identity check below can never pass there, and if it did pass it would
mean the withheld work shipped.*

- After `git fetch origin`, `git diff --stat origin/main origin/develop` prints **only what the
  reopen commit carries** — at minimum step 22's four files: `plugin/VERSION`,
  `plugin/.claude-plugin/plugin.json`, `pyproject.toml` and the
  `.prawduct/changes/release-vX.Y.Z.md` fragment. Post-cut bookkeeping folded into the same commit is expected beside
  them and is not a Phase 2 failure: the v3.5.0 cut added the release plan's `Status:` line and this
  runbook's own step 11a, for seven files. **What makes the difference readable is step 17**, which
  proved content identity *before* the promotion; anything appearing here arrived after it, on
  `develop` only. If you skipped step 17, you cannot tell the two apart from this line alone.

  > **This bullet used to say "prints nothing", and Phase 3 is what changed it.** Content
  > identity is the expected outcome of Phase 2, and step 22 deliberately advances `develop`
  > past it one commit later. A check that can never pass on a correct release is worse than
  > no check: the operator learns to expect the failure and stops reading it. If it prints
  > anything *else*, Phase 2 did not finish. Run it before step 22 to get the strict form.
- `git ls-remote --tags origin` shows a line ending `refs/tags/vX.Y.Z`.
- `./plugin/bin/prawduct-hook check-released vX.Y.Z` prints `released: vX.Y.Z — 3 of 3 verified`
  and exits 0. It checks the three things this phase just did — version files agreeing
  at the tag's tree, the tag contained in `origin/main`, the Release published — so run
  it instead of re-typing them. **Exit 3 is not a pass:** it means a check could not run
  (no `gh`, no `origin/main`, or a declared `toml` version file on a pre-3.11 python3 — this
  repo declares one), and the Releases page may still be empty. Repo-local on purpose —
  the *installed* plugin is the previous release and does not carry this subcommand.
- The `verify-release` workflow run dispatched at step 21 is green
  (`gh run list --workflow verify-release.yml --limit 1`). It runs the same command with a token,
  so it is the check that still happens on the release where someone skipped the bullet above.
  A red run here means the release is incomplete — it never means CI failed to publish something,
  because CI does not publish. **A red run is a fact about the release, not a suspect workflow:**
  this job has been exercised both ways — green against the real v3.2.4 tag with output identical
  to the local command, red with a `not-released` verdict against a deliberately bogus one. There
  is no longer any reading of red that lets you carry on.
- Your own install holds the released **`plugin/` subtree**, not the prep one — these two print the
  **same** 40-character sha:

  ```
  echo "released:  $(git rev-parse vX.Y.Z:plugin)"
  echo "installed: $(git rev-parse "$(python3 -c "import json,os,pathlib;p=pathlib.Path(os.environ.get('CLAUDE_CONFIG_DIR','~/.claude')).expanduser()/'plugins/installed_plugins.json';print(json.loads(p.read_text())['plugins']['prawduct@prawduct'][0]['gitCommitSha'])"):plugin")"
  ```

  > **Trees, not commits — and that is the whole check, not a nicety.** `main` is built by
  > `git read-tree --reset -u origin/develop` plus a fresh commit (steps 15–16), so a release tag
  > shares `develop`'s tree and **never** its commit identity. A commit-sha comparison here is
  > therefore not a strict check that occasionally annoys you; it is a check that **cannot pass**,
  > on any release, for any correct install resolved from `develop`.
  > *(Fixed at v3.3.4, #646. Measured at v3.3.3: installed `gitCommitSha` `f7394808`, released
  > `v3.3.2^{commit}` `1f65e231`, and both whole trees `09791bd1` — identical.)*
  >
  > **And the `plugin/` subtree rather than the whole tree, because that is what installs.**
  > `.claude-plugin/marketplace.json` declares `source: ./plugin`, so the cache holds that subtree
  > and nothing else. Comparing whole trees would report a mismatch for any commit after the release
  > that touched only `.prawduct/` — which is nearly every session, since governance state is
  > committed constantly — while the installed content is byte-identical to what shipped. `:plugin`
  > compares exactly the content under test. *(#646 shipped the whole-tree form; the subtree
  > narrowing landed in the same cycle, from the Critic's R-12.)*

  > **This is the one `Done when` item that is not a fact about the release.** The other four
  > grade what you published; this one grades **your machine**, and a mismatch is compatible
  > with a perfect release. It also has more than one cause — see *If this doesn't work*
  > below, which is where the three get separated. Do not read a differing sha as "the release
  > is wrong."

## If this doesn't work

- **If a step doesn't match what you're seeing:** stop where you are.
  Everything before step 19 is undoable, so stopping costs nothing but time,
  and a step that doesn't make sense is a defect in this document, not in you.
- **If the two shas in `Done when` differ:** there are **three** causes and they need different
  responses. Read `installPath` and `version` out of `plugins/installed_plugins.json` first —
  they are what tell the three apart. In every case the release itself is fine and consumers are
  unaffected: this is a `directory:` marketplace symptom, local to you.

  0. **`version` is a *prerelease* (`3.4.1-dev.2`, anything with a `-`)** — **nothing is wrong, and
     the triage command below cannot grade it.** Your marketplace resolved `develop`, so the cache
     is keyed on a version that has no tag; `git rev-parse "v${installed_ver}:plugin"` fatals with
     `invalid object name` and the `||` branch then prints **case 2 or 3**, which is a false verdict
     of exactly the shape #646 removed — it routes a correct install at the delete-the-cache remedy.
     The check that *does* apply is whether the cached plugin is the plugin that version names:

     ```
     [ "$(git show "${installed_sha}:plugin/VERSION")" = "$installed_ver" ] \
       && echo "cache holds the plugin its own key names — prerelease, case 0"
     ```

     A prerelease key is abandoned by the cut in both directions (`main` is now the release,
     `develop` is now the *next* prerelease), so it can never be re-resolved and the next session
     picks up whichever ref your marketplace points at. Do nothing. *(Measured at v3.5.0: installed
     `3.4.1-dev.2` at `151751b2` on `develop`, whose `plugin/VERSION` is `3.4.1-dev.2` exactly.)*
  1. **`version` is the *previous* release, and no cache directory exists for the new one** —
     **nothing is wrong.** Your install is simply still on the last release and re-resolves at
     the next session start. This is the ordinary state immediately after a promotion, because
     the session you cut the release from began before the release existed. Start a new session
     and re-check; do nothing else. *(Measured at v3.2.5: installed `3.2.4`, no `3.2.5` cache
     directory, shas differ, release verified 3 of 3.)*

     > **First clean run of the corrected test, v3.3.4.** Installed `3.3.3`, no `3.3.4` cache
     > directory, `Done when` pair differs (`abafac96` released vs `e123dd1a` installed) — and the
     > triage below printed **case 1**, because `c7a3ebf2:plugin` and `v3.3.3:plugin` are both
     > `e123dd1a`. The cache held the v3.3.3 plugin exactly. This is the measurement #646 was
     > written for: the removed `merge-base --is-ancestor` form would have called this same correct
     > install a NON-release tree and sent the operator to delete the cache. The v3.2.5 note above
     > was taken *with* the broken test, which is why it could only report "shas differ" and never
     > reach a case.

     > **The `Done when` pair MATCHING, measured from a fresh session — v3.3.4, 2026-08-12.**
     > `released` and `installed` both `abafac9677e2ac2ca3fc116311386af1cf2d3cef`. This is the
     > first end-to-end confirmation the check has ever produced: every prior measurement was
     > taken from the cutting session, where a mismatch is correct-and-expected (case 1) and the
     > pair therefore *cannot* match. Taking it from a later session is what makes a match
     > meaningful, and it closes the loop the v3.3.4 note above could only open — the pair
     > differing at the cut and matching a day later is exactly the auto-update working. A
     > mismatch here would have been the first genuine (2)/(3) ever seen; it was not.
  2. **`version` is the new release, and the sha is the *prep* commit** — the failure this bullet
     was written for. The cache was filled during the Phase 1–2 gap, and it will not refresh on
     its own because the version key never changed between prep and promotion. Fix it before you
     test anything against "the release."
  3. **`version` is a release, but the cached plugin is not that release's plugin** — a `develop`
     subtree cached under a *release's* version key. Same class as (2), different route: no
     Phase 1–2 gap involved, just a session that resolved a `directory:` marketplace while
     `develop` was checked out. Mechanically possible and it would be silent, so the case stays.

     > 🔍 **NEVER OBSERVED — and its one "live instance" was a false positive, twice over.**
     > The v3.2.5 sighting (`plugins/cache/prawduct/prawduct/3.2.4` at `a0c2468`) was produced by
     > the `merge-base --is-ancestor` test #646 removed, which fails for every install. Re-measured
     > at v3.3.4 against whole trees it appeared to survive (`165e315f` vs `fa827756`) — but whole
     > trees were the wrong unit too, and against the unit that actually installs it collapses:
     > **`a0c2468:plugin` and `v3.2.4:plugin` are both `ba3e8581`.** That cache held the v3.2.4
     > plugin exactly; only `.prawduct/` had moved on, which it does every session.
     > **Do not cite `a0c2468` as evidence of anything.** If you ever do observe a real case (3),
     > record it with `:plugin` shas and delete this box.

     *Recorded at length because the instance survived two corrections before dying: each new test
     was run against the previous test's conclusion rather than against the question.*

  The test that separates (2) and (3) from (1). Run it only after ruling out (0) — a `-` anywhere
  in `installed_ver` means the tag it names does not exist and this command's verdict is noise:

  ```
  installed_sha=$(python3 -c "import json,os,pathlib;p=pathlib.Path(os.environ.get('CLAUDE_CONFIG_DIR','~/.claude')).expanduser()/'plugins/installed_plugins.json';print(json.loads(p.read_text())['plugins']['prawduct@prawduct'][0]['gitCommitSha'])")
  installed_ver=$(python3 -c "import json,os,pathlib;p=pathlib.Path(os.environ.get('CLAUDE_CONFIG_DIR','~/.claude')).expanduser()/'plugins/installed_plugins.json';print(json.loads(p.read_text())['plugins']['prawduct@prawduct'][0]['version'])")
  [ "$(git rev-parse "${installed_sha}:plugin")" = "$(git rev-parse "v${installed_ver}:plugin")" ] \
    && echo "cache holds the released plugin — case 1" || echo "cache holds a NON-release plugin — case 2 or 3"
  ```

  > **Why subtree equality and not ancestry.** The old form asked
  > `git merge-base --is-ancestor <installed-sha> v<installed-version>`, which tests commit
  > lineage. `main` never has one to `develop` — steps 15–16 build it by `read-tree` plus a fresh
  > commit — so that test returned false for **every** install, including correct ones, and could
  > only ever print "cache holds a NON-release tree". It routed correct installs into (2)/(3) and
  > the delete-the-cache remedy below. `:plugin` is the unit because that is what the marketplace
  > ships; see the `Done when` bullet above. *(Fixed at v3.3.4, #646.)*

  **Remedy for (2) and (3):** delete the cache directory named by `installPath` and start a new
  session.

  > 🚧 **UNVERIFIED** — the *detections* above are all measured, including the case (3) instance.
  > The **re-resolve remedy** has still not been executed. Confirm the shas match afterwards
  > before trusting it.
- **Escalate to:** this repo has one maintainer, so escalating means stopping —
  leave `develop` as it is and come back to it. An unfinished release is
  invisible to consumers.
- **Act immediately if:** you pushed `main` and then found something wrong.
  Consumers pick `main` up at their next session start, so the fix is a new
  release with a higher version — a revert without a version bump does not
  ship.
