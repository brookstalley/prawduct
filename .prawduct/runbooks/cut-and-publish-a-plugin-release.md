---
runbook: cut-and-publish-a-plugin-release
tier: 3
owner: prawduct maintainer
last_verified: null
verified_by: null
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

**Read the scope list, not the exit code.** Two outcomes matter:

- **It names one or more release-pending scopes** — change-log entries tagged
  `scope=` with no `release=`. That set is the unreleased content. **Proceed.**
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
which is where those two verdicts actually differ.

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
      recorded decision, not a reflex: record it in the release plan or the
      change-log entry.

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

   **Expected:** `releasable: vX.Y.Z — N release-pending scope(s), M shipping, K withheld`,
   followed by the two lists. **Note `K` — it selects the promotion shape at Phase 2.**

   **Also exit 0, but different:** `releasable: no release-pending scopes — nothing to classify`.
   This line names no version and yields **no `K`**; read it as `K = 0`. Reaching it *during* a
   release contradicts this runbook's own entry condition, so treat it as a symptom, not a pass:
   either Phase 1 already ran (its step 3 stamps `release=`, which empties the pending set), or the
   entries you expect carry no `scope=` key and are invisible to the gate. Check which before
   continuing.

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
   - The table and the change log disagree about what is shipping. **Do NOT delete the row** — that
     makes the gate pass and ships the very scope the table withheld. Decide which is true and fix
     the other: drop the `release=` tag, or reclassify the row as `ships`.

   `cannot-verify-blockers:`
   - This repo has cut over to the GitHub Issues backlog, so `backlog.md` is frozen history and
     blocker liveness cannot be read from it. **Confirm each withholding blocker is open by hand**
     and record that confirmation in the release plan beside the classification table. Then proceed
     — the gate stays red by design and the recorded hand check is what replaces it. **Blocker
     liveness is the only thing it withholds**: every other check still ran, so fix any other
     `ERROR:` line printed beside this one before proceeding.

   `unreadable-project-state:`
   - The gate cannot tell which backlog is live, so it cannot judge blocker liveness either.
     **Fix or restore `.prawduct/project-state.yaml`**, then re-run. (This is not the cutover case —
     the message says so precisely because the two need different remedies.)

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

   ```markdown
   ## Release classification

   | Scope | Disposition | Blocker |
   |---|---|---|
   | coverage-perf | ships | |
   | v3.2.0-golive | withheld | BKL-6J2X |
   ```

   > ⚠️ **A scope with no `release=` tag that in fact shipped long ago will appear here.** That is
   > not a false positive — it means no record says which release carried it, which is precisely
   > what makes "what did the last release ship?" unanswerable from this file (REL-7D4X's root, and
   > the `learnings.md` rule that a previous release's contents are determined from its **code**,
   > never from change-log prose). Backfill the `release=` tag on those entries using the code test
   > in Phase 1 step 2, rather than classifying history into the release you are cutting now.

---

## Phase 1 — Release prep on `develop`

1. List the tagged change-log entries, newest first:

   ```
   grep -n "<!-- prawduct:" .prawduct/change-log.md | head -20
   ```

   **Expected:** numbered tag lines, newest first, at least one carrying
   `release=v...`.

2. Find the boundary — the topmost line whose tag carries `release=`. That's
   the previous release.

   **Expected:** one line number and a version, like
   `745:<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->`.

   > ⚠️ **The boundary narrows the search. It does NOT define the set — do not
   > flip "everything above it" (REL-7D4X).** An entry lands where it merged,
   > not above the last release, so a genuinely unreleased entry can sit
   > *below* the boundary and a positional sweep drops it silently. This
   > happened at v3.1.1: `2026-07-14: Stale remote-base diagnostics` sits below
   > and had to be flipped.
   >
   > **The sound test is per candidate:** an entry is release-pending iff it
   > carries no `release=` tag **and** its code is absent from the previous
   > release's tree (`git show <prev-tag>:<path>`). Walk every untagged entry
   > and apply it. Entries predating the tag convention (roughly pre-2026-06)
   > are untagged but shipped — the code test is what separates them.

   > ⚠️ **The set also spans SCOPES — narrowing the sweep to one `scope=` drops
   > the rest just as silently.** A release bundle routinely carries several, so
   > re-deriving the set with `grep 'scope=<the-one-you-remember>'` returns a
   > subset that looks complete. **Step 0 already printed the full list** — the
   > release-pending scopes it enumerated are the scopes to walk here. Use that
   > output; do not re-derive it from memory.
   >
   > Count them rather than recalling them — the number moves every time work
   > merges. This enumerates every scope with a statusless entry, **whole file,
   > no boundary restriction**:
   >
   > ```
   > grep -o '<!-- prawduct:[^>]*-->' .prawduct/change-log.md | grep -v 'release=' \
   >   | grep -oE 'scope=[A-Za-z0-9._-]+' | sort | uniq -c | sort -rn
   > ```
   >
   > It deliberately **over**-includes: entries below the step-2 boundary land in
   > it too, and the per-candidate code test above is what filters them. Over-
   > inclusion is the safe direction here — the failure being prevented is a
   > scope you never looked at.
   >
   > To reproduce the figures below, restrict it to the boundary first:
   >
   > ```
   > sed -n "1,$(( $(grep -n '<!-- prawduct:.*release=' .prawduct/change-log.md | head -1 | cut -d: -f1) - 1 ))p" \
   >   .prawduct/change-log.md | grep -o '<!-- prawduct:[^>]*-->' | grep -v 'release=' \
   >   | grep -oE 'scope=[A-Za-z0-9._-]+' | sort | uniq -c | sort -rn
   > ```
   >
   > *(The boundary pattern must be the **tag line** `<!-- prawduct:.*release=`, not a
   > bare `release=` — this file's own prose contains that string, and a bare match
   > lands the boundary in a paragraph near the top and returns almost nothing.)*
   >
   > Measured that way on `feature/rel-8p6m-releasability-gate` @ `1a353d1`:
   > **23 release-pending entries across six scopes**, of which
   > `scope=v3.2.0-golive` is only **7** — so that one grep misses **16 across
   > five other scopes** (`release-readiness` 7, `coverage-perf` 4,
   > `chunk-refs-gate` 2, `critic-disposition` 2, `review-loop-termination` 1).
   > One of the missed entries is the `protected_path_violation` widening, a
   > change to the governance bounds of every installed repo. Step 10's
   > consumer-facing headline is derived from **all** shipping scopes, so a
   > scope-narrowed sweep quietly shortens the release notes as well as the tags.
   >
   > *(Any figure written here is a measurement of one tree, not a property of
   > the repo. Re-run the commands rather than citing this paragraph.)*

   > 🚧 **If this selection rule looks wrong to you, it is — and it is
   > deliberately not being fixed here.** The positional-and-scoped sweep is
   > REL-8P6M (e), **held** by owner decision 2026-07-29:
   > `artifacts/change-log-ledger-design.md` proposes deleting this machinery
   > outright, so rewriting the rule now is throwaway work. **That decision was
   > taken 2026-07-31 — GO on the design, HOLD on the schedule (§11.7) — so the
   > hold survives and only its bound moved: it now runs until the ledger plan
   > is scheduled and shipped.** Until then, this release tags its shipping
   > subset **by hand across every scope, once**. `REL-7D4X` stays open with it.

3. Append ` | release=vX.Y.Z | status=shipped` to every tag line that passed the
   step-2 test, keeping the keys already there and the ` | ` separator:

   ```diff
   - <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 -->
   + <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 | release=v3.2.0 | status=shipped -->
   ```

   > *Why: a tag line left statusless ships nothing — no checkbox flip, no
   > release-notes entry — and nothing downstream complains.*

4. Re-run the enumeration and read down to the boundary:

   ```
   grep -n "<!-- prawduct:" .prawduct/change-log.md | head -20
   ```

   **Expected:** every line above the step 2 boundary now carries
   `| release=vX.Y.Z | status=shipped`.

5. Regenerate the derived views. **There is no pre-flight and no dry run** —
   validation runs inside this one command, before any write, so the separate
   check step this runbook used to carry could never catch anything this does
   not. Read the exit code; it is the whole signal:

   ```
   prawduct-hook regen-views
   ```

   **Expected:** exit 0.

   **If it exits 2:** nothing was written. A *global* tag error — an
   unrecognized `status=`, or conflicting tag lines — is on stderr as `ERROR:`
   lines. Fix those tags in `.prawduct/change-log.md` and re-run this step.

   **If it exits 3:** views **were** written, but at least one scope's
   `## Status` was withheld because its own tags do not validate (a `chunks=`
   ID matching no roster entry, an unreleased scope with no plan file, a
   duplicate `scope:`). stderr names each. **This is a release blocker even
   though views were written** — fix those tags and re-run until it exits 0.

6. Confirm the views actually landed. Run `git status` and read step 5's stdout.

   **Expected — all of:**
   - one `Status (artifacts/<plan>.md): N chunk(s) flipped — shipped [...]`
     line per release-pending plan
   - `Release notes: write release-notes.md`
   - a `Scope rollups: ...` line
   - the corresponding files dirty in `git status`

   **If not:** a `Status (...): up to date` line where you expected a flip means
   that plan's `chunks=` tags matched nothing → back to step 3. **Check
   `git status` first**: after a successful step 5 a re-run prints `up to date`
   for everything because it genuinely is, and reading that as "the tags matched
   nothing" sends you to re-edit correct tags.

   > *Why: the build-plan checkboxes, release notes and scope rollups are all
   > derived here — hand-edit them and the next regen reverts you.*

7. In `plugin/VERSION`, replace the old number with the new one, without the `v` — `3.2.0`
   for a `v3.2.0` release.

8. In `plugin/.claude-plugin/plugin.json`, replace `"version"` with the same
   number.

   > *Why: that string is the update cache key. A release that forgets it does
   > not ship, however clean the push.*

9. In `pyproject.toml`, replace `version = "3.0.3"` with the same number.

   > *Adjudicated, not derived: the file's own comment asks for this bump;
   > `documentation/release-process.md` step 2 didn't name it until v3.1.1.*

10. In `plugin/CHANGELOG.md`, add a `## vX.Y.Z` section directly above the previous release,
    with the consumer-facing headline as the first non-empty line under it.

    > *Why: the version-delta banner shows exactly that first line to every repo
    > crossing this version.*

11. In `.prawduct/project-state.yaml`, set `active_build_plan:` to `null`.

12. Commit the prep:

    ```
    git commit -am "release: prep vX.Y.Z"
    ```

    **Expected:** `[develop <sha>] release: prep v3.2.0`.

13. Push it:

    ```
    git push origin develop
    ```

    **Expected:** a line ending `develop -> develop`.

    > *Why: Phase 2 builds `main` from `origin/develop`. Anything still local
    > won't be in the release.*

### Checkpoint

`origin/develop` now holds the whole release: bumped version, shipped
change-log tags, regenerated views, cleared plan pointer. Everything up to here
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
- **Stop here.** Go to `.prawduct/runbooks/promote-a-pruned-release.md`, which replaces steps 14–20
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

16. Commit it on `main`, using the headline you wrote at step 10:

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

20. Tag the release and publish the tag:

    ```
    git tag vX.Y.Z && git push origin vX.Y.Z
    ```

    **Expected:** `* [new tag]  v3.2.0 -> v3.2.0`.

    > *Chained on purpose: if the tag already exists, `git tag` fails and the
    > push must not run.*

21. Publish the GitHub Release, using step 10's whole CHANGELOG section as the notes:

    ```
    awk '/^## vX.Y.Z$/{f=1;next} /^## v/{f=0} f' plugin/CHANGELOG.md > /tmp/notes-vX.Y.Z.md
    gh release create vX.Y.Z --title vX.Y.Z --notes-file /tmp/notes-vX.Y.Z.md
    ```

    **Expected:** one line — the release URL, ending `/releases/tag/vX.Y.Z`.
    **If the notes look truncated or carry the previous release's text:** the `awk`
    boundary missed. Check that `## vX.Y.Z` is on its own line in `plugin/CHANGELOG.md`
    with nothing trailing it, then re-run with `gh release edit` rather than `create`.

    > *Why the whole section, not just the headline: `plugin/CHANGELOG.md` ships **inside**
    > the plugin, so it is unreadable to anyone who has not installed it. The Releases page
    > is the only public copy. A pushed tag alone lands on `/tags` and nowhere else, leaving
    > `/releases` reading "no releases published" — which is both where a consumer whose
    > banner just announced an update goes to find out what changed, and the first thing
    > someone evaluating prawduct sees.*

---

## Done when

*These are the **whole-develop** tests. A pruned promotion left this document at Phase 2 and has its
own `Done when`: the content-identity check below can never pass there, and if it did pass it would
mean the withheld work shipped.*

- After `git fetch origin`, `git diff --stat origin/main origin/develop` prints
  nothing.
- `git ls-remote --tags origin` shows a line ending `refs/tags/vX.Y.Z`.
- `./plugin/bin/prawduct-hook check-released vX.Y.Z` prints `released: vX.Y.Z — 3 of 3 verified`
  and exits 0. It checks the three things this phase just did — version files agreeing
  at the tag's tree, the tag contained in `origin/main`, the Release published — so run
  it instead of re-typing them. **Exit 3 is not a pass:** it means a check could not run
  (no `gh`, no `origin/main`), and the Releases page may still be empty. Repo-local on purpose —
  the *installed* plugin is the previous release and does not carry this subcommand.
- The `verify-release` workflow run for the tag is green
  (`gh run list --workflow verify-release.yml --limit 1`). It runs the same command with a token,
  so it is the check that still happens on the release where someone skipped the bullet above.
  A red run here means the release is incomplete — it never means CI failed to publish something,
  because CI does not publish.
- Your own install holds the released tree, not the prep tree — these two print the
  **same** 40-character sha:

  ```
  echo "released:  $(git rev-parse vX.Y.Z^{commit})"
  echo "installed: $(python3 -c "import json,os,pathlib;p=pathlib.Path(os.environ.get('CLAUDE_CONFIG_DIR','~/.claude')).expanduser()/'plugins/installed_plugins.json';print(json.loads(p.read_text())['plugins']['prawduct@prawduct'][0]['gitCommitSha'])")"
  ```

## If this doesn't work

- **If a step doesn't match what you're seeing:** stop where you are.
  Everything before step 19 is undoable, so stopping costs nothing but time,
  and a step that doesn't make sense is a defect in this document, not in you.
- **If the two shas in `Done when` differ:** your install cached the prep tree under
  this release's version key during the Phase 1–2 gap, and will not refresh on its
  own because the key never changed. The release itself is fine and consumers are
  unaffected — this is a `directory:` marketplace symptom, local to you. Fix it before
  you test anything against "the release."

  > 🚧 **UNVERIFIED** — the remedy is to delete the cache directory named by
  > `installPath` in `plugins/installed_plugins.json` and start a new session. The
  > *detection* above is measured; this re-resolve has not been executed. Confirm the
  > shas match afterwards before trusting it.
- **Escalate to:** this repo has one maintainer, so escalating means stopping —
  leave `develop` as it is and come back to it. An unfinished release is
  invisible to consumers.
- **Act immediately if:** you pushed `main` and then found something wrong.
  Consumers pick `main` up at their next session start, so the fix is a new
  release with a higher version — a revert without a version bump does not
  ship.
