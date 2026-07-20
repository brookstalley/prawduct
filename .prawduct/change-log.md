# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

## 2026-07-20: `--archive-scope open` stops promising a backup that cannot exist; A1 decided `all`

<!-- prawduct: type=fix -->
<!-- Statusless = release-pending once develop→main ships. No scope= tag: a
     doc/claim correction plus one decision record; no build plan, no ## Status. -->

Two things, one root. Deciding prawduct's own `--archive-scope` (release-plan **A1**) meant reading
what the lever actually does — and the documented case for `open` turned out to be false.

**The false claim.** Every surface describing `open` said the skipped archive "stays as the MG2
export file." It cannot. `export_backlog` dumps the **migrated repo**, and the runbook's step 0 puts
it *after* the first import — so by construction the export never contains what `--archive-scope
open` excluded. An operator choosing `open` on that basis would expect a restorable archive artifact
that was never produced.

The truth is narrower but real: skipped items stay in the **git-tracked source markdown**, which is
step 0's pre-migration backup. What no surface said is the part that actually decides the choice —
post-cutover, `skills/backlog/SKILL.md` treats that file as frozen history and stops reading it, so
the skipped set is **git history, not live backlog**: outside post-cutover `list`, and outside
add-time dedup, so a duplicate of a previously-dropped item can be re-filed with no signal. (Stated
as `list` rather than `find` — full-text `find` is W2-deferred for *every* post-cutover item, so it
is not what archive scope costs. An earlier draft of this entry said `find`/`list`, which was the
same overstatement in the opposite direction.) Corrected at the parent requirements first (PRD MG4 + requirements §MG4b), then the
downstream surfaces, then the shipped change-log entry that recorded it — **ten claim sites across
seven files**, a figure derived by enumerating the diff rather than counted by eye, because three
earlier drafts of this very entry stated it three different ways.

**Guarded, not just fixed.** The `open` warning string now has a test asserting the sentence is
*true* — it must not credit "export" and must name the source markdown — verified to fail against
the old wording before being trusted. This class of defect (a plausible, reassuring safety claim) is
invisible in review precisely because it reads well, so it gets a mechanical check rather than
another resolution to be careful.

**A second operator-facing correction, found the same way.** Once the docs stopped over-promising,
the obvious next sentence — "so re-run with `--archive-scope all` to backfill" — turned out to carry
its own unstated cost. It is true that the re-run creates no duplicates (the skip authority is the
`id:PFX` alias written in the create). It is *not* a free top-up: the skip path still reconciles the
status axis, so a backfill drives every already-migrated item back to its **markdown** status,
reopening anything closed on the service since cutover. The runbook now states both halves and tells
the operator to treat a backfill on a live repo as a migration in its own right; a test pins the
reopen so the claim can't quietly stop being true.

**Left alone, deliberately:** the *restructure* rollback claims ("recoverable via the MG2 export
backup") are true — `original_title`/`original_body` are written into the issue block, so the
post-import export does carry them. Same words, different mechanism; checked rather than assumed.

**A1: `all`** (`artifacts/migration-scrub-decisions.md` decision 5). The deciding argument was
default-path coverage, not archive completeness: `all` is the flag's default, so choosing `open` for
the dogfood would ship the default path unexercised by the one migration prawduct runs itself. This
promotes **`BKL-6X5D` part (b)** from conditional to a firm v3.2.0 blocker — an archived item costs a
paced create plus an **unpaced** close, so the archive leg is the half-metered stretch part (b)
exists to close. The runbook had back-attributed an `all` decision to a file written 16 hours before
the flag existed; that citation now points at the real decision.

The residual product gap — `open` genuinely does strand the archive outside the live tracker — is
filed as **`BKL-4Z7M`**, adopter-facing and not release-gating now that prawduct takes `all`.

`documentation/backlog-service-{prd,requirements}.md`, `lib/backlog/{migrate,cli}.py`,
`skills/backlog/migration-scrub.md`, `tests/test_backlog_migrate.py`,
`tests/test_backlog_invariants.py`, `.prawduct/artifacts/build-plan-backlog-service.md`.

*(The guard has two halves: `test_backlog_migrate.py` asserts the value actually emitted at runtime,
and `test_backlog_invariants.py::TestArchiveScopeWarningTruthfulness` scans every such literal in
`lib/backlog/`, so a third emission site cannot inherit the old wording while a per-site test stays
green. The second half is the one that caught the `cli.py` site the first half missed.)*

## 2026-07-20: Two contradicting conventions adjudicated into norms; the cutover sweep becomes re-greppable (skills-cutover-awareness Chunk 04)

<!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 -->

The residue the inventory found, plus the two conventions Chunks 02–03 left contradicting with
nothing deciding between them. Both are now `## Direction` norms with owners, because "nothing owns
the rule" is why the next reader copies whichever file it happens to open.

**No prawduct-internal ids in operator-emitted text** (`observability-strategy.md`). The dormancy
NOTE all three readers copy ended "(GV8; restored with the read-through cache)" while a test asserted
those same ids must *not* appear in the advisory's `recommended_action` — the same audience, the same
unresolvable pointer, opposite rules. Ruled for the test's reasoning and applied it everywhere: the
NOTE now ends "they return when the backlog read-through cache lands," which is what the id stood
for. The sweep at birth found five in-scope sites (the three NOTE copies, `adapter-mode.md`'s emitted
`find` NOTE, and `probe_checks_dormant`'s advisory evidence — moved in-scope by cumulative finding
R-10, since the changeset that wrote it is the changeset that birthed the norm) and **six more
outside this changeset**, so the norm is born
`Status: in-transition` tracking **OBS-7M4D** rather than claiming a clean inventory. The heuristic
(id-shaped tokens in string literals) is not exhaustive — prefixes are open-ended — so the durable
enforcement is the reviewer's judgment, recorded as such.

**`backlog_service_repo` selects the authoritative store; direct reads are gated, not banned**
(`data-model.md`). `skills/pr/SKILL.md` said *never* read the file directly; `skills/janitor/SKILL.md`
explicitly permitted it pre-cutover. A blanket ban was considered and rejected — it would retire the
janitor's full-body overlap read with no live replacement, which is the bespoke per-reader projection
the read-through cache exists to avoid. The PR copy is corrected to the gate; both readers state it
inline (Chunk 01's contract: a reader loading one file gets the whole rule).

- `skills/backlog/SKILL.md` — owns the direct-read rule, including the rejected alternative;
  Archive split (Q2) and `find` are scoped to the markdown backend rather than reading as
  unconditional from the shared preamble.
- `lib/upstream_probes.py` — the triage advisory names *the backlog*, not `.prawduct/backlog.md`,
  so it stops misdescribing the destination the moment a report-receiving repo cuts over.
- `tests/test_cutover_prose_coherence.py` (new) — pins the three NOTE copies to one invariant tail,
  pins the gate in every reader, and makes the sweep **re-greppable**: a skill naming `backlog.md`
  must either mention `backlog_service_repo` or sit on an allowlist with a stated reason, and a
  `lib/` module pathing to the file must carry a cutover guard. The original sweep called itself
  exhaustive and had missed `skills/pr/SKILL.md`; this is what catches the next miss.

**From the cumulative review** (0 blocking, 9 warnings — all resolved). Three were defects this
chunk's own charter should have caught: the always-injected `session-digest.md` states the
`## Archive` workflow unconditionally — and, per the follow-up review, *no* root list would have
found it, because the digests never name `backlog.md` at all; they are pinned by their own test, and
the sweep's widening to `methodology/`/`agents/`/`templates/`/`docs/` is future coverage rather than
the fix (recording that honestly rather than taking the tidier story);
`.prawduct/cross-cutting-concerns.md` still
claimed the norm-lifecycle probes as live coverage over a hole this bundle documents; and all four
`skills-cutover-awareness` change-log tag lines were space-delimited where `lib/views.py` splits on
`|`, so `scope=`/`chunks=` never parsed and the release would have silently lost the feature's
attribution. Also: the janitor and PR skills instruct `/prawduct:backlog list` but granted no
`backlog` subcommand, so post-cutover both stated routes were closed — the grants are added. The
dormancy enumeration now derives from one `DORMANT_CHECKS` list rather than a hand-maintained string
plus a hardcoded "7", and `docs/norms.md`'s migrate arm gains the completed-at-birth case that the
`data-model.md` norm legitimately takes.

**One finding declined, with reason.** The review asked that `skills/critic/review-protocol.md`
restate the dormancy rule in full rather than summarizing it, on the premise that a reviewer subagent
may never open `review-cycle.md`. `agents/critic-reviewer.md:30` routes the one reviewer that runs
Backlog Reconciliation — sustainability — to `review-cycle.md` explicitly, so the gate is not behind
an unfollowed reference; and `review-protocol.md` sits at deliberately near-zero token headroom, so
the restatement would have cost ~175 tokens of reviewer context on every review to fix a hypothetical.
The routing is what's load-bearing, so the routing is now what's pinned.

**Classification:** governance

## 2026-07-20: Janitor Backlog Health states dormancy; the overlap read is repointed (skills-cutover-awareness Chunk 03)

<!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=03 -->

The janitor's three backlog touchpoints, split by what each actually does with the data — the
discriminator this chunk had to sharpen before it could be built:

- **Step 2.5 Backlog Health — dormant.** All seven checks are section-shaped (group by `area:`, dedup
  by overlap, staleness, unstaged `stage:`, `## Promoted` neglect, legacy-item count, `## Archive`
  growth). Two were worse than stale: check 6 proposed `/prawduct:backlog migrate` and check 7 an
  archive split, both meaningless once Issues is system of record — advice a reader could act on to
  no effect. The block now emits one "unavailable" line rather than being omitted; an absent section
  reads as a clean bill of health, which is the failure being replaced.
- **Step 1 Orient and Step 7 Close — repointed.** Both go through `/prawduct:backlog list` /
  `/prawduct:backlog`, which route to whichever backend is live.

**The rule that decides which treatment a reader gets** — Chunk 02's "dormancy is for readers with no
live path" under-determined this chunk, because `list` *can* approximate two of the seven checks. The
sharper test: **repoint a reader that consumes the item view as-is; declare dormant a reader that
derives a verdict from it.** Rebuilding a health check on a list call is the bespoke per-reader
projection the owner decision rejected, and an approximation labelled as a health check is the
confident-wrong-answer failure in a new costume.

Two defects the review surfaced, filed rather than folded in: **JNT-4R2M** (janitor instructs
`prawduct-hook review-stats` with no matching `allowed-tools` grant — invisible in this checkout
because `Bash(python3 *)` reaches the hook by the self-hosted path) and **BLD-7K3Q**
(`verify-chunk-refs` derives the current chunk from the first unchecked `## Status` box, so on a
`views_enabled` branch it grades Chunk 01 all branch long and reports `ok` for files it never read).

## 2026-07-20: The PR path stops resolving `closes:` against frozen markdown (skills-cutover-awareness Chunk 02)

<!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=02 -->

Chunk 01's dormancy contract, copied to the three backlog readers in the PR path. **R-2 is the
highest-risk reader in the whole inventory**: it is the sole owner of the
change-log-says-`closes:`-but-item-is-open consistency check — no Critic layer runs it — so
post-cutover it resolved every `closes:` against frozen history and either passed or dangled with
equal confidence. R-1 was written against `## Open`/`## Promoted` sections that do not exist on the
Issues backend at all.

- `skills/pr/review-protocol.md` — R-1/R-2 gain the same backend precondition the Critic carries:
  read `backlog_service_repo` (already read at step 1), and when set, skip both and emit one
  "unavailable" NOTE. R-1's markdown-section wording is now backend-neutral.
- `skills/pr/SKILL.md` — the prep-while-Critic-runs step is **repointed, not declared dormant**:
  `/prawduct:backlog list` has an adapter path on both backends, so retiring the step would have
  been a loss. Dormancy is for readers with no live path, not for every surface naming the file.
- VRF-008 gains a `/prawduct:pr create` step and no longer drains on a Critic run alone — a Critic
  run never dispatches the PR reviewer, so it left R-1/R-2 unexercised while reading as coverage.

The chunk was planned `doc-only` and re-typed to `code`: `test_pr_reviewer.py` asserted `"always
run" in content`, which kept passing on a substring of prose that now says "always run **on this
backend**" — the opposite of what the test's docstring claimed. A test that keeps passing while its
stated contract inverts is worse than one that fails, so the assertion was scoped and the new
precondition pinned alongside it.

## 2026-07-19: Backlog-check dormancy is stated, not silently wrong (skills-cutover-awareness Chunk 01)

<!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=01 -->

`/prawduct:backlog` routes on `backlog_service_repo`; the other backlog readers do not. The Critic's
Backlog Reconciliation and C-B1–C-B4 read `.prawduct/backlog.md`, which is frozen history once a
project cuts over — so every item archived at cutover still parses as open and every live Issue is
invisible. Three norm-lifecycle probes have the mirror failure: they guard on cutover and return
nothing. Both shapes are indistinguishable from a clean bill of health, and the norm-probe half means
norm exceptions stop expiring visibly. Recorded as **GV8** after the owner ruled the loss a side
effect rather than a decision.

This chunk ships the interim contract only — restoring the checks in Issues mode waits on the W1
read-through cache, one persisted format, per the owner decision not to mint a bespoke projection now
and migrate off it later.

- New `backlog-checks-dormant` probe (`info`, dismissible) fires post-cutover and names all seven
  dormant checks, so anyone dismissing it knows what they are choosing to run without.
- Critic `review-cycle.md` / `review-protocol.md` gain a backend precondition: when
  `backlog_service_repo` is set, skip the walk and emit one "unavailable" NOTE. The check is a `Read`
  of project state, not an adapter call — `critic-reviewer` grants no Bash by design (CRT-3X9D).

**Also landed here: GV9, a new requirement** (`documentation/backlog-service-requirements.md` § GV9).
Writing GV8's interim contract exposed the layer below it — after cutover the canonical id is
`owner/repo#number`, but every surface that *cites* an item (`_BACKLOG_ID_RE`, Critic C-B4, PR `R-2`,
`closes:`/`closed-by:` tags, the deferred build-plan ref check) recognizes only `PFX-XXXX`, so a
post-cutover reference is not mis-read, it is **not seen** — GV8's silent-degradation shape one layer
down. Recognition is additive and can ship early; *resolving* a reference to a live status is a
backlog read and lands with W1 under GV8. No code here implements it; the requirement is recorded so
the gap stops being invisible. Tracked for build as **BKL-4R7V**.

Two things the review process caught that are worth keeping. `review-protocol.md` sat exactly at its
3529-token ceiling, and the first attempt to pay for the addition deleted Goal 4's norms line as
redundant — `test_project_preferences_blocking` proved it load-bearing, and the tokens came from
compressing Goal 7's close instead. And repointing the stale `active_build_plan` immediately failed a
chunk-heading guard, which turned out to be a drifted *test* rather than a plan defect (TST-6K3D).
## 2026-07-20: `--archive-scope` becomes discoverable, and stops being credited with the rate ceiling (BKL-6X5D part a)

<!-- prawduct: type=fix -->
<!-- Statusless = release-pending once develop→main ships. No scope= tag: a
     two-surface fix with no build plan, so there is no ## Status to regenerate. -->

Found while sizing a real migration of hallucinote's backlog (~87 open items) — both defects
changed the advice being given about that migration, which is how they surfaced.

**The flag was honored but never advertised.** `--archive-scope {all,open}` is parsed and applied by
both `import` and `restructure-preview`, and neither listed it in `--help`. Both usage lines now
carry it.

**Scoped honestly** (Critic note): MG4's "explicit owner-confirmed choice surfaced at scrub time" was
*not* defeated — `skills/backlog/migration-scrub.md` steps 2c/3 already name the flag, its tradeoff,
and the corrected Pacer attribution, so an operator following the runbook always saw the choice. The
real gap is narrower: CLI discoverability for anyone arriving outside the runbook — reading `--help`
to see what `import` accepts, which is exactly how this was found. Worth fixing, not worth
dramatizing.

The guard is a **parity test, not a string assertion**: it reads which handlers resolve the selector
(`ast` over `lib/backlog/cli.py`), maps them through the `op ==` dispatch chain, and asserts each
resulting op's help line names the flag.

That mapping only reads the single-literal `op == "x"` shape, and `cli.py` already dispatches two ops
as `op in ("get","show")` / `op in ("link","unlink")` — so a future honoring op added in that shape
would have been silently dropped from the reviewed set while the suite stayed green. A second
**orphan check** closes it: every handler that honors the flag must appear in the mapped set, else
the test fails and demands the derivation be extended rather than degrading quietly. Both tests were
verified to fail against a deliberately broken tree — a parity test that passes before and after
would have been worthless.

**The docstring taught the mis-attribution BKL-6X5D exists to correct.** `apply_archive_scope` said
`open` keeps "a large migration inside the write-rate budget (NF3)." It does not: the **Pacer** holds
the ceiling by pacing creates across time whatever the volume, and the archive lever reduces total
write *volume*. The requirements were corrected on 2026-07-18; **six** further surfaces still carried
the old framing — and being the nearest source to the code, the docstring is what a reader reaches
for first. All six are corrected here.

**Six surfaces, found across four rounds — and the process record is the point, because three of
those rounds ended in a closure claim that was wrong.**

| round | found by | surfaces |
|---|---|---|
| 1 | me | `apply_archive_scope` docstring, PRD §8.9 |
| 2 | Critic (chunk) | PRD §9/NF3 |
| 3 | Critic (verify-resolutions) | NFR §3.3 `:146`, PRD §11/S3 `:249` |
| 4 | Critic (verify-resolutions) | NFR §9 `:287` |

Round 1 ended with me writing that leaving a sibling copy would be the "patch the flagged line, not
the class" failure — while leaving PRD §9 in the same file, at the exact anchor the rewritten §8.9
sends readers to. Round 2 ended with "correct in every surface"; round 3 found two more, one of them
in a file that same round had just added to the item's `refs:`. Round 3 ended by publishing a
falsifying grep in the backlog note *with the instruction to run it before claiming coverage* — and
then claiming coverage without running it. Round 4 is that grep, finally executed, returning
`nfr.md:287`.

`:287` was the most load-bearing of the six: it is the **S2 proof obligation**, so "migration burst
fits after scrub" would have aimed the dry-run at post-scrub volume instead of at the Pacer. It now
states the obligation as proving the Pacer holds the burst — measured with the volume lever
*disabled* (`--archive-scope all`), since a small input proves nothing about pacing — and adds the
create-then-close 900 pts/min question (part b) as a second thing S2 must answer.

**No exhaustiveness claim is made here.** Six is the count swept, not proof there is no seventh. The
falsifying query lives in BKL-6X5D's note for whoever next wants to assert coverage:
`grep -rn 'scrub' documentation/*.md | grep -i '500\|rate\|budget\|fit\|trim'` — the remaining hits
read correctly as of this commit. The honest lesson, recorded rather than tidied away: stating the
discipline does not execute it — **three** consecutive rounds of self-certification (1, 2 and 3) were
each closed by an external reviewer instead. Round 4 is the exception that shows the shape of the
fix: it made no closure claim, and the thing that produced it was running a query rather than
resolving to be careful.

*Counting note, since this entry is about miscounts:* the review of round 4 caught this very sentence
claiming **four**. Round 4 was the one round that did *not* self-certify, so "four" overstated the
lesson by including its own counterexample. Corrected. Note also that this entry and BKL-6X5D's note
partition the same work differently — the entry counts six surfaces *this changeset touched* (the
docstring plus five doc sections, excluding the requirements text corrected on 2026-07-18); the
backlog note counts six *documentation* surfaces (including requirements, with the docstring listed
separately as the code surface). Both totals reconcile at seven, and both enumerate their members in
place, so either can be checked rather than trusted.

Fixing §9 also dissolves the **§8.9↔§9 circular reference** BKL-6X5D tracked separately: §8.9 now
credits the Pacer and cites §9, and §9 credits the Pacer and cites NFR §3, so neither defers to the
other for the ceiling. NFR §3's row additionally now names the **unmetered create-then-close
stretch** (part b) instead of implying the scrub makes the burst safe.

The docstring also
records the volume reason the Pacer genuinely does not cover: archived items cost *two* writes each
(create-then-close), because the create path has no initial-state field.

PRD §8.9 additionally described the lever as "migrate only a recent-shipped window," which is the
*unbuilt* refinement — the shipped lever is the binary `{all,open}` (MG4b), and the window remains
BKL-6X5D's deferred quantification work. Corrected so the PRD stops describing an unbuilt design as
current.

**Still open in BKL-6X5D:** the window **quantification** (N-months / a throughput formula), and
part **(b)** — metering total REST points (5/write, 1/read) against 900/min for the create+close
archive stretch. Part (a) closes entirely here: both the re-attribution *and* the §8.9↔§9
circularity.

**Part (b) is no longer adopter-scale-only.** It is filed as "not gating the dogfood," which held
while the dogfood was small. The escalation rests on a **structural** property, not a headcount:
under `--archive-scope all` each archived item costs a create *and* a close, and
`pacer.before_create()` is annotated "the only paced call" — so the archive stretch runs
create-then-close with **half of it unmetered**, which is precisely the >900 pts/min window part (b)
describes. Its only mitigation today is *incidental* `gh`-subprocess latency, explicitly "not
designed-in" and forfeited by the raw-HTTP fast-path (D2/W1). Under `--archive-scope open` there is
no archive stretch at all and the gap stays theoretical. Re-scoped accordingly: **gating for any
`all`-scope migration at portfolio scale**, still deferred for `open`.

*An earlier draft of this paragraph justified the escalation with "383 open + 124 archive = 507
creates, past the 500/hr cap" — a 1.4% margin resting on a number I had not verified was stable. The
PR reviewer challenged it against the 317 figure the documents this changeset edits still carry.
Checking, discodon's four checkouts report **384 / 389 / 349 / 319** open, and the canonical one read
383 then 384 twenty minutes apart. The count is not a fact; it is a live instance of the
stale-views-across-checkouts pain (#2) this whole project exists to kill, and it cannot carry a
gating decision. The argument above needs no count — only that the unmetered stretch exists —
which is true at 317 and at 389. Recorded rather than silently re-numbered, because the failure was
using an unverified figure as load-bearing evidence, not picking the wrong one.*

## 2026-07-19: SessionStart banner names which plugin code is loaded (BRF-7Q4M)

<!-- prawduct: type=feature -->
<!-- Statusless = release-pending once develop→main ships. No scope= tag: a
     single-surface feature with no build plan, so there is no ## Status to regenerate. -->

The identity banner printed only `═══ Prawduct v3.1.0 (plugin) ═══`. Because `VERSION` and
`plugin.json` move only at release-prep, an integration branch carrying unreleased work reports the
same version as the release it was cut from — `develop` and `main` both read 3.1.0 while develop
carried ~380 unreleased commits. An operator testing that work in another repo via
`claude <target> --plugin-dir ../prawduct` had no signal telling them whether the local checkout or
the marketplace copy actually loaded. The hazard is real, not theoretical: `init-product` scaffolds
`enabledPlugins: {"prawduct@prawduct": true}`, and a settings-managed force-enable is documented to
win over `--plugin-dir`.

The identity line now carries a load-provenance segment — `(plugin · develop@24e4210+dirty)` — when
the plugin root is a working tree, and stays byte-identical for a managed install. Its presence is
itself the discriminator: a managed install can never print it, so seeing it proves the local
checkout won.

Two design points worth keeping:

- **The gate is a path comparison, not a `.git` probe.** A marketplace install is itself a git clone
  (`~/.claude/plugins/marketplaces/<name>/.git`), so "has a `.git`" does not distinguish the two.
  Provenance is computed only when the plugin root falls outside the managed plugin directory
  (`CLAUDE_CONFIG_DIR`-aware), which is also what keeps the git subprocess off the SessionStart hot
  path for every ordinary user — measured at ~65 ms, paid only by local-checkout loads.
- **One `status --porcelain=v2 --branch --untracked-files=no` call** yields ref, oid and
  tracked-file dirtiness together (~36 ms) versus ~105 ms for separate `rev-parse`/`diff` calls, and
  `--untracked-files=no` is what makes untracked scratch files correctly not count as dirty.

Fails open throughout: a managed install, a non-git root, an unborn branch, or any git failure
degrades to the plain banner rather than breaking session start. Detached HEAD renders as
`detached@<sha>`.

Two asymmetries make the degradation honest rather than merely quiet. A probe that was *expected*
to produce a segment and could not (git missing, unrunnable, or past the 5s timeout) reports the
cause on stderr — absence of a segment otherwise reads as "a managed install won", which is the
mis-diagnosis the feature exists to prevent; the genuinely-nothing-to-report paths stay silent,
because for them empty is the truth. And an unresolvable plugin path is treated as *managed*, not
as a checkout: the opposite choice would route a real managed install into the git probe, which
succeeds (marketplace installs are clones) and would render a segment — making presence stop being
proof.

Files:
- `hooks/banner.py`: `managed_plugin_home`, `is_managed_install`, `_git`, `checkout_provenance`;
  identity line composes the suffix.
- `skills/ping/SKILL.md`: echo the banner's parenthesised part verbatim — normalising the segment
  away would answer the very question a ping is asked.
- `tests/test_plugin_version_banner.py`: `TestManagedInstallDetection`, `TestGitRunner`,
  `TestCheckoutProvenance`, `TestBannerIdentityLine` (20 cases, real git fixtures) — including a
  managed-install-with-`.git` case that pins the path gate against regression to a `.git` probe, a
  byte-for-byte assertion that the managed-install banner is unchanged, negative cases pinning that
  the quiet paths stay quiet while the expected-but-failed path names its cause, and a guard that an
  unexpected `_git` return takes the reported path rather than raising out of the hook. Full suite
  2444 passed.

## 2026-07-19: verify-chunk-refs stops flagging `path:line` citations and same-chunk `new` re-references

<!-- prawduct: type=fix -->
<!-- Statusless = release-pending once develop→main ships. No scope= tag: a plain
     two-item bugfix with no build plan, so there is no ## Status to regenerate. -->

Two `verify-chunk-refs` false-positive variants in `lib/buildplan_refs.py`, closing `BLD-4V7Q` and
`BLD-6T4R`. Both live in `_parse_build_plan_chunk_refs`'s token loop and land together; they were
filed separately because they sit at different layers (token shape vs. exemption reach).

- **`path:line` citations existence-checked literally** (`BLD-4V7Q`): the loop stripped a
  `::symbol` suffix but not a `:452` / `:5-8` one, so a backticked code-location citation like
  `lib/critic_mode.py:452` was checked as the whole string and reported `missing-ref` against a file
  that was present. Both suffixes now go through one helper, `_ref_path_part`, which splits on `::`
  *first* so a digit-tailed symbol (`lib/rules.py::rule42`) isn't mistaken for a line number. The
  suffix pattern also covers the editor-style `path:line:col` (`lib/foo.py:12:34`) — no corpus
  instance today, but it is the same citation shape and cost one optional group to include.
- **`new ` forward-ref exemption was line-local** (`BLD-6T4R`): the exemption keyed on the token's
  start offset, so a path declared `new` on a Deliverables line flagged as missing whenever the
  chunk named it again — a Done-when step, typically. The qualifier is now collected across the
  whole chunk section into a per-path set, normalized the same way as the tokens, so a `new`
  declaration also covers a later `path:line` citation of it. Still per-path and per-chunk: one
  `new` declaration doesn't silence other missing refs in the section, and doesn't leak to siblings.

Verified against the real plan corpus, not just fixtures — parsing every chunk of every
`.prawduct/artifacts/*build-plan*.md` under the pre- and post-fix parser. Five plans change: three
`path:line` citations resolve to their files (`build-plan-gate-hardening` Chunk 02,
`v2.0.0-plugin-distribution` Chunk 5), and three `new`-declared paths stop being flagged on
re-reference. 12 regression tests; suite 2408 passed / 6 skipped.

**A known cost, accepted here.** Two of those three dropped refs sit in chunks already marked `[x]`
shipped: `lib/backlog.py` (`build-plan-backlog-rework` Chunk 01) and `methodology/agent-stance.md`
(`build-plan-rigor-and-stance` Chunk 02). Both were genuinely built, then restructured away — the
parser into the `lib/backlog/` package, the stance doc folded into the digest by prose-diet Chunk 03
— so the plans still name paths nothing lives at. Neither is a delivery failure, but both are real
drift, and the old parser was surfacing them: *true* positives, caught incidentally because those
chunks happened to re-reference the path. The chunk-scoped exemption now silences them, because it
is unconditional with respect to chunk completion — once a chunk ships, its declared-new deliverable
is never existence-checked again. That contract gap is filed as `BLD-8R3T` (gate the exemption on
the chunk still being open; it needs `BLD-9H2M` first, or re-arming the check turns that
false-negative into a false positive), and the two stale paths as `BLD-5N7C`. Both corrections came
from the Critic, which caught this entry's first draft citing the two paths backwards as *false*
positives.

A **third** false-positive variant surfaced during the corpus check and is filed, not fixed
(`BLD-9H2M`): the qualifier regex is matched per line, so a soft-wrapped `… new\n  \`path\``
declaration is never detected at all — visible in `build-plan-backlog-service.md` Chunk 01.
Out of scope for both items fixed here.

Reviewing this branch also turned up a false claim in `.prawduct/cross-cutting-concerns.md`: the
Build-plan ref drift row asserted "building.md: builder runs `verify-chunk-refs` before marking
chunk done," but `methodology/` never mentions the command — the gate is Critic-run only. The row is
descriptive, so it now records the absence; whether building.md *should* carry that step is
`BLD-4Q8W`, filed at `stage: requirements` because the answer is a decision, not code.

## 2026-07-19: Salvage stranded work from the removed backlog-service worktree branch (worktree-salvage)

<!-- prawduct: type=fix -->
<!-- Statusless = release-pending once develop→main ships. No scope= tag: this is a
     plan-less fix branch, and a statusless scope must resolve to a build-plan file
     whose ## Status can be regenerated (lib/views.py). -->


Two linked worktrees were retired (`prawduct-wt-backlog-prd`, a clean duplicate `develop` checkout;
`.claude/worktrees/backlog-service-plan`). The latter's branch carried ~2,900 lines of backlog-service
implementation **superseded** by the `lib/backlog/` package that shipped on develop (Chunks 01-06) —
plus a handful of changes that existed nowhere else. Those are salvaged here; the superseded layout
(`lib/backlog_service.py`, `lib/backlog_github.py`, `bin/prawduct-backlog`, their tests, and the v1
design artifacts) is deliberately dropped.

- **Digest single-copy checks filter relative to root** (`tests/test_plugin_methodology_digest.py`):
  `.git`/`.claude` were filtered on ABSOLUTE path components, so a checkout that itself lives under a
  `.claude/worktrees/` session worktree had its *canonical* digest excluded along with the strays,
  breaking the single-source assertion. Now filtered on components relative to `root`.
- **Worktree fork-write pollution rule** (`.prawduct/learnings.md`): a `/prawduct:*` skill fork writes
  `.prawduct/` state to the LAUNCH dir, not a worktree the session ENTERED mid-session — so a
  state-mutating skill silently dirties a different active worktree's WIP and reports success.
- **Four backlog items** an ID-set diff proved existed only on the removed branch: `ENV-7C4K`
  (bare `prawduct-hook` resolves to the stale plugin cache, silently no-opping BOTH Critic
  data-plane writes — `critic-begin` and the SubagentStop `critic-consolidate`), `STH-7W9K` (the
  fork-write gap above; filing it resolves the learnings rule's dangling pointer), `VWS-2W6H`
  (plan discovery has no `artifact: build-plan` filter), `BLD-6T4R` (the `new` forward-ref exclusion
  is line-local, not chunk-scoped). `VWS-2W6H`/`BLD-6T4R` were re-verified live in code before filing.

Three defects the Critic surfaced during this salvage were inherited from already-merged work rather
than introduced here, and were fixed in place (owner-approved) rather than deferred:

- **Shadowed dead `current_branch`** (`lib/gitstate.py`): a second definition sat above the
  pre-existing one, and Python's later-binding made it unreachable — every caller *and* the three
  tests added alongside it ran the older `symbolic-ref` probe. Both returned the branch name or
  `None` on detached HEAD, so deleting the dead copy is a runtime no-op (suite unchanged at 2396
  passed). The entry below claiming a "new" probe is corrected in place.
- **`regen-views` failing closed** (`.prawduct/change-log.md`): two statusless entries carried a
  `scope=` tag resolving to no build-plan file. Since `regen-views` writes **no** views on any
  error, that blocked `## Status` regeneration for every release-pending plan at the develop→main
  release. Both tags dropped; `regen-views --check` now passes.
- **VRF-007 asked for an impossible step** (`.prawduct/operator-verification.md`, `DOC-4K9M`): Verify
  step 3 told the operator to round-trip a field change via `--if-updated-at`, which the skill cannot
  do — the `get` envelope exposes no `updated_at` — while the document's own pre-verification note
  already recorded the step as dropped. Step 3 now verifies a normal-path round-trip (a title/stage/
  area edit reflected by a following `get`/`list`) and records the omission so it cannot be silently
  re-added. The reworded step is itself **unverified** until Phase 1 (`BKL-6M4T`) executes VRF-007.

## 2026-07-19: /prawduct:backlog skill repointed onto the GitHub-Issues adapter (backlog-skill-repoint)

<!-- prawduct: type=feature | scope=backlog-skill-repoint | chunks=01,02 -->
<!-- Statusless on feature/backlog-skill-repoint = release-pending once develop→main ships. -->

**BKL-3W6K.** The GH-Issues migration built the `prawduct-hook backlog` adapter and repointed the
briefing + advisory probes, but the everyday `/prawduct:backlog` **skill** stayed markdown-native (no
`Bash` in `allowed-tools`) — so post-cutover `pick`/`add`/`list`/`update` would drive the *frozen*
markdown, not the Issues that are now system-of-record. This repoints it.

- **Dual-mode dispatch** (`skills/backlog/SKILL.md`): a top-level "Backend routing" gate reads
  `backlog_service_repo` from `project-state.yaml` — unset → the existing markdown path
  (byte-unchanged for pre-cutover consumers); set → the new `adapter-mode.md` runbook. Adds a scoped
  `Bash(prawduct-hook backlog *)` grant.
- **Adapter runbook** (new `skills/backlog/adapter-mode.md`): maps each subcommand onto an adapter op
  (add→`file`, list→`list`, pick→`pick`, update→`status`/`update` with the `promoted`→`in-progress`
  status-vocabulary bridge, claim/link, summary→`counts`, get→`get`), and owns the envelope/exit
  discipline — binds to exit codes + the `--json` envelope (surfacing `warnings[]` on **both** the ok
  and error envelopes), and **fails loud** on auth/unavailable (never a silent fall-back to the
  frozen markdown).
- **Deferred (owner-decided — ships after W2):** `find`/`dedup` need the W2 search op → a clear
  "lands in W2" NOTE, no degraded search; `migrate`/`scrub`/archive-split → a
  not-applicable-post-cutover NOTE.
- Cumulative Critic 0 blocking / 0 warning / 7 note (actionable notes resolved). Adapter loop
  pre-verified live against a throwaway repo (reads/writes/`promoted`→`in-progress` bridge/exit-3/
  exit-4); VRF-007 remains pending the sibling-*session* confirm. Markdown path unchanged when
  `backlog_service_repo` is unset. Phase 0 of the migration program; Phases 1 (sibling dogfood) and 2
  (prawduct self-cutover) follow.

## 2026-07-18: Stop hook surfaces the silent worktree `.prawduct/` redirect (stop-worktree-redirect-note)

<!-- prawduct: type=feature -->
<!-- Statusless: observability feature on develop, ahead of the batched develop→main release.
     No scope= tag (dropped 2026-07-19): a statusless scope must resolve to a build-plan file
     whose ## Status can be regenerated, and this shipped as a plan-less branch — the tag made
     regen-views fail closed, and it writes NO views on any error. -->

**STH-3R8K.** `get_project_dir()` follows a session into a git worktree, resolving
`.prawduct/` state to the worktree toplevel rather than `CLAUDE_PROJECT_DIR`
(STH-4K7N). That redirect failed safe but *silently* — the Stop gates could
evaluate a different tree than the launch dir with no announcement, and a wrong
redirect (should the cwd-is-the-worktree assumption ever break) would mis-gate
invisibly. The Stop path now makes it observable.

- **Signal** (`bin/prawduct-hook`): new `_worktree_redirect_note(project_dir)`;
  `cmd_stop` prints one stderr line — `WORKTREE: .prawduct/ state resolved to
  worktree <path> for branch <b>, not CLAUDE_PROJECT_DIR <env> — the Stop gates
  read THIS worktree` — exactly when the resolved dir differs from the env pin.
  Emitted before gate logic; informational only, never a blocker. Silent on the
  single-checkout / launched-in-worktree path (no redirect, no noise).
- **Probe** (`lib/gitstate.py`): the existing reusable `current_branch(project_dir)`
  (read-only `git symbolic-ref --quiet --short HEAD`, fail-open — `None` on
  detached HEAD / non-repo) supplies the branch label. (Corrected 2026-07-19: this
  entry originally claimed a *new* helper. A second definition was in fact added
  above the existing one, where Python's later-binding made it dead code — every
  caller and all the tests below ran the pre-existing `symbolic-ref` probe. The
  dead duplicate is now deleted; behavior was and remains that of the live one.)
- **Scope call**: the SessionStart digest/banner surface (named in the item's
  refs) was deliberately scoped out — SessionStart runs in the launch dir and
  cannot observe a mid-cycle worktree move, and would duplicate BRF-6K2D. The
  Stop path is the only load-bearing surface (Critic-validated).
- Regression tests (`tests/test_project_dir_resolution.py`, +7):
  `current_branch` (worktree / primary / detached / off-repo), the note
  (fires-on-differ, silent-on-equal, silent-on-env-unset), and `cmd_stop` wiring.

## 2026-07-18: discodon upstream defect fixes (discodon-upstream-defects)

<!-- prawduct: type=bugfix | scope=discodon-upstream-defects | chunks=01,02,03,04 -->

**Parent:** four prawduct defects filed upstream by the discodon product (their ids
CRT-M3F8, PDT-C6R4, CRT-T9RX, PDT-WT9K), re-verified against `develop` (v3.1.0) by direct
code read + three independent verification agents. Audit of the 9-defect batch: 5 fully
fixed (CRT-W2NV, CRT-J4PM×2, CRT-8F3K, CRT-K7VF), TEV-9K2M core fixed with a by-design
`--scope`/`--from-counts` residual; the four below had remaining work. Local items:
CRT-4T7M (newly filed), BLD-5J8N, CRT-7H2W, CRT-6W2N. Plan:
`.prawduct/artifacts/build-plan-discodon-upstream-defects.md`.

**What (chunks built so far):**
- **Chunk 01 — CRT-M3F8 / CRT-4T7M (critic-consolidate file-less/blank findings):**
  `validate_partial` now rejects a finding's `files` only when it is not a list at all;
  blank/non-string elements are normalized out in `merge_findings` (`[""]` → no `files`
  key, exactly like `[]`). A reviewer's file-less META-finding (Learnings Cross-Check /
  Backlog Reconciliation) no longer fail-closes the entire consolidation. The strict
  derived-cache validator (`_validate_critic_findings_data`) is untouched — tolerant at the
  reviewer-input boundary, strict on internally-generated data. Regression tests:
  blank/all-blank/non-string elements accepted + normalized; non-list `files` still rejected.
- **Chunk 02 — PDT-C6R4 / BLD-5J8N (verify-chunk-refs header parsing + loud parse-miss):**
  the shared `lib/buildplan_refs.py` chunk parsers (`_chunk_section_lines`,
  `_chunk_id_from_item_text`, `_current_chunk_id_from_status`) now match both the
  `### Chunk NN:` and `## Chunk N (ID) — Name` (H2, em/en-dash, optional `(ID)`) forms via
  `_CHUNK_HEADING_RE`/`_CHUNK_ITEM_RE` — the id must be followed by a separator/paren/EOL so a
  notes sub-heading (`### Chunk 2 build-session decisions`) is not mistaken for a boundary.
  This fixes both the Goal-2 deliverable gate AND `infer-critic-mode`'s chunk lookup (they share
  the primitives — the GOV-8N4V facet). `cmd_verify_chunk_refs` now emits a distinct
  `cannot-verify:` (gate could not run) vs `missing-ref:` (deliverable absent), curing the
  false-negative habituation. The `regen-views`/`CHUNK_LINE_RE` colon-Status residual is filed
  as VWS-2F9K (not silently expanded); the colon-form learning was updated. Verified via a
  3-case CLI exercise (located+ok / missing-ref / cannot-verify) on an H2 fixture.
- **Chunk 03 — CRT-T9RX / CRT-7H2W (intent-aware verify-resolutions head anchor):**
  `begin_review`'s verify-resolutions branch now reads intent from git: when a COMMITTED delta
  exists since the prior review (`critic_mode._committed_files_since`), it anchors
  `head_tree = capture["head_tree"]` (committed HEAD — the PR-gate target) and note-and-excludes
  WIP like the cumulative branch; otherwise it keeps the working-tree anchor (the Stop-hook
  target), preserving CRT-4J8W dirty-tree verify. So a post-cumulative fix that carries a stray
  judgeable uncommitted file no longer leaves `check-cumulative-critic` `uncovered` after a
  successful verify-resolutions. Diagnostic half of the CRT-7H2W layered pair also shipped: a
  judgeable-WIP WARNING at record time and a dirty-tree hint in the gate's `uncovered` remedy.
  Tests: manifest anchors committed HEAD in the committed-delta case + keeps the working tree
  otherwise (both notes asserted); an end-to-end gate-composition proof in `test_cumulative_gate.py`.
  Final-mode Critic: 0 blocking; 2 warnings addressed (note tests added; plan `path:line` citations
  reformatted and the ref-token `:line` over-match filed as BLD-4V7Q).
- **Chunk 04 — PDT-WT9K (critic-begin worktree visibility + refuse-on-unresolvable):** the dangerous
  silent-wrong-tree root cause was already fixed (cwd-follow via `resolve_project_dir`); this adds the
  hardening. `begin_review`'s manifest now carries `worktree`/`branch` (nullable; `branch` None on a
  detached HEAD, via the new `gitstate.current_branch`); `cmd_critic_begin` prints the resolved
  worktree/branch/base and lists sibling worktrees so a wrong tree is obvious, and REFUSES when the
  shell's git repo differs from the resolved review tree; `cmd_infer_critic_mode` names the resolved
  tree on stderr (stdout `<mode>|<rationale>` unchanged for the skill parser). `briefing._get_current_branch`
  now delegates to `gitstate.current_branch` (de-duplicated, keeps its 'main' display default). Chunk
  Critic: 0 blocking; 2 warnings addressed (detached-HEAD/nullable-validate edge tests added; the
  "branch-elsewhere surfaced not blocked" reinterpretation recorded as a plan DECISION).
- **Cumulative review (whole branch, 0 blocking / 0 warning / 7 note):** post-cumulative resolution —
  the sibling-worktree listing's `w['branch']` subscript could `KeyError` on a bare-repo worktree
  entry (git emits `bare`, not a `branch`/`detached` line); made it defensive with `.get('branch','?')`
  like `briefing`'s own consumer. Backlog reconciled: CRT-4T7M, BLD-5J8N, CRT-7H2W flipped shipped
  (closed-by this branch); CRT-6W2N kept open with a partial-progress note.

## 2026-07-18: Backlog service — resumable import envelope keeps its audit warnings (backlog-service)

<!-- prawduct: type=bugfix | scope=backlog-service-v1 -->
<!-- Statusless: bugfix on the importer resume path ahead of the deferred live leg (BKL-6M4T). -->

**BKL-9V2W.** `migrate.import_items`' resumable mid-run error envelope (the
TransportError path) carried `created`/`skipped`/`collisions` but dropped the
accrued `warnings[]` — so an alias self-heal audit line emitted by an
already-completed record was lost, and never re-emitted on resume (the restored
`id:PFX` label makes the record skip the fast path, so the heal never re-runs).
The live-migration audit trail must not lose these.

- **Data plane** (`lib/backlog/migrate.py`): the resumable error envelope now
  carries the accrued `warnings[]` at top level (matching the ok envelope).
- **CLI** (`lib/backlog/cli.py`): the human-mode *error* path now surfaces
  `warnings[]` like the ok path — a carried-but-unprinted warning would still be
  invisible to the operator running the migration.
- **Contract** (`documentation/backlog-service-api-contract.md` §3): notes that a
  resumable error also carries top-level `warnings[]`.
- Regression tests: `test_resumable_error_carries_accrued_self_heal_warnings`
  (data plane) + `test_error_envelope_warnings_reach_stderr` (CLI emitter).

## 2026-07-18: Backlog service — owner-feedback gap-fills (backlog-service)

<!-- prawduct: type=feature | scope=backlog-service-v1 -->
<!-- Statusless: four PRD/owner-review gaps closed offline ahead of Chunk 06's deferred
     live leg; flips no chunk checkbox (06 stays deferred — BKL-6M4T). -->

Four gaps surfaced in owner review of the backlog-service design, closed on
`feature/backlog-prd-owner-feedback` (all offline, fake-transport-tested; the live
migration leg stays deferred):

- **MG4b — `--archive-scope {all,open}` lever.** The importer now honors an
  owner-confirmed archive-scope choice: `all` (default, pre-scrub behavior — every
  archived item becomes a closed issue) or `open` (migrate only the live/open set;
  the historical archive stays in the git-tracked source markdown, minting no closed
  issue per ancient item — fewer total writes, NF3; the Pacer, not this lever, enforces
  the write-*rate* ceiling — BKL-6X5D). *(Corrected 2026-07-20: as shipped, this entry
  was one of ten claim sites saying the skipped archive "stays as the MG2 export." It cannot —
  `export` dumps the migrated repo post-import. Fixed in the entry above.)* Surfaced as an explicit owner question in
  the migration-scrub runbook (new step 2c); `restructure-preview` honors the same
  scope so the owner reviews exactly what imports. Quantified recent-window between
  the poles stays BKL-6X5D (adopter-scale). `lib/backlog/{migrate,cli}.py`.
- **XP2 — `prawduct-hook version` provenance source.** A new `version` subcommand
  prints the running plugin's bare semver from the bundled manifest, so upstream
  bug reports stamp `Found in: prawduct vX.Y.Z` **sourced, not recalled** (a
  recalled version drifts). `skills/report-bug` now sources it; pinned into the
  backlog-service Chunk 06 (MG5) and upstream-bug-reporting acceptance criteria.
- **Issue standard — self-filed bug provenance.** The bug `Env` line is now
  *recommended* (product version + environment), and a WARN-only `bug-missing-env`
  lint nudge fires for a `kind:bug` issue with no Env line — never blocks (advisory
  posture). `lib/backlog/issuefmt.py`, issue-standard §2/§4.
- **GV7/MG3 — migration-required advisory + `legacy.py` retirement-gate fix.** A new
  warn-priority `backlog-service-migration-required` advisory fires while a
  *structured* markdown backlog has live items and `backlog_service_repo` is unset —
  so a repo that upgraded past prawduct's own cutover is told to migrate, never
  silently degraded. It partitions cleanly with `legacy-backlog-format` (pre-structured
  → format nudge; structured → service nudge). The build plan's `legacy.py` retirement
  is corrected: as the **shared** plugin's markdown read path it retires only at
  portfolio-wide migration (MG3), not at any one project's cutover. `lib/backlog_probes.py`.

## 2026-07-17: Backlog service — GitHub Issues as the system-of-record (backlog-service)

<!-- prawduct: type=feature | scope=backlog-service-v1 | chunks=01,02,03,04,05 -->
<!-- Statusless on feature/backlog-prd-owner-feedback = release-pending once merged.
     Large subsystem; plan at .prawduct/artifacts/build-plan-backlog-service.md, one
     commit per chunk, per-chunk Critic. Chunk 06's OFFLINE deliverables ride in this
     entry (must-fixes, restructure pre-pass, transport blockers) but 06 is deliberately
     NOT tagged: its live-migration leg is deferred (owner hold, BKL-6M4T), so the 06
     Status checkbox must not flip at release. -->

**Parent:** BKL-5D2C — replace the markdown backlog (slow, merge-conflict-prone, git-coupled;
the deepest measured pain being stale/untrusted item state) with **GitHub Issues as the
system-of-record** via a deterministic `prawduct-hook backlog` adapter (PRD §16 item 6).

**What (chunks built so far):**
- **Chunk 01 — walking skeleton:** the `lib/backlog/` package (transport seam + in-process
  fake, `file`/`get`, minimal `provision`), the `bin/prawduct-hook backlog` dispatch, and the
  markdown parser moved to `legacy.py` (all readers repointed). Live round-trip verified (VRF-004).
- **Chunk 02 — two-axis status state machine (CC1/M5 keystone):** crash-safe idempotent
  `set-status` (state-authority-first, add-before-remove, self-healing reconciliation), `update`
  (optimistic CAS → `conflict`, SEC-2 mass-assignment guard, block-preserving body edits), and
  `comment`. Live status path queued as VRF-005.
- **Chunk 03 — query & ready-work (GV1/DM3/CC3):** the read side in a new `lib/backlog/query.py`
  (`list` structured filters/sort/paginate online off the REST list endpoint; `pick` list-then-fan-out
  — assignee/claim-TTL + native-blocker predicates, cross-repo blockers judged from a live read,
  ranked + *why*; `counts` derived on read), plus `claim`/`unclaim` (atomic take-and-verify in one
  PATCH — crash-safe, TTL-reap so `pick` can't starve) and `link`/`unlink` (native dependencies +
  sub-issues + a block-list `related`) in `core.py`. PROV-2 (non-prawduct issues ignored) and the
  observed 404-after-create replication window (bounded settle-retry) handled. Live `list`/`pick`
  round-trip queued as an L5 smoke.
- **Chunk 04 — governance surface (GV2/GV6/SEC-5/SEC-6):** `refresh-counts` (the `briefing_counts`
  degenerate cache — a schema-versioned JSON snapshot at `<git-common-dir>/prawduct/`, atomic write,
  visible age, network-independent) in a new `lib/backlog/snapshot.py`; `reconcile-labels` (GV6
  coexistence reconcile — create-missing, foreign labels untouched, idempotent); the never-block floor
  (a backend-down `unavailable` never hangs/corrupts); and the unattended-context guards (SEC-5
  Actions write-withhold, SEC-6 `automated`/`worker` marking) in a new pure `lib/backlog/context.py`.
  The D6 detached-refresh warm rides `transport.spawn_detached` (egress discipline). L5 smokes queued.
- **Chunk 05 — importer + alias machinery + minimal `merge` + `export` (MG1/MG2/DM4/AU3):** a new
  `lib/backlog/migrate.py` — `import` (idempotent/resumable, keyed on the permanent `id:PFX` alias
  written atomically in the create; a durable checkpoint accelerator; no rollback, M6), the alias
  machinery (`ids.py`: `PFX-XXXX` → `id:PFX` label + `id_aliases` block + redirect-follow), a minimal
  `merge` (fold A→B, **redirect-before-close** so a crash leaves the source open-but-redirected —
  CRASH-2; nothing hard-deleted), `export` (full-fidelity JSON dump incl. the native graph — deps,
  sub-issues, timeline, assignees), and a write-`Pacer` (content-budget 80/min+500/hr, injectable
  clock). Transport/fake gained `list_sub_issues`/`list_timeline`; the export on-disk layout is pinned
  in Data Model §8. Fixture-proven (MIG-1…4, CRASH-2/CRASH-4); the live SPIKE-S2 + real migration stay
  in Chunk 06. `import`+`export`+`merge` L5 smokes + the Done-when-0 live blocker check queued.
- **Chunk 06 pre-sign-off must-fix BKL-4W7H (offline part, 2026-07-17):** closed the `id:PFX`-alias
  self-healing gap. `core.resolve_ref` wires PFX→canonical alias resolution into `get`/`link` (against
  `--repo`); `migrate._find_by_key` gains a block-`id_aliases` fallback skip-authority (`_AliasIndex`,
  one lazy scan per drifted run) that self-heals the missing label so a human-deleted `id:PFX` can't
  turn a re-import into a permanent duplicate; `reconcile-labels` re-derives deleted aliases from the
  block. The live migration (SPIKE-S2, dogfood, briefing/gate repoint, drop-box retirement) stays in
  Chunk 06 (BKL-6M4T).
- **Chunk 06 must-fixes BKL-7Q2N + BKL-3K9N (2026-07-17):** the remaining single-id mutators
  (`status`/`update`/`comment`/`claim`/`unclaim`) plus `merge` source/target now resolve a bare
  `PFX-XXXX` through `core.resolve_ref` with a threaded `default_repo` (closing the MG1
  "existing IDs stay valid forever" gap `get`/`link` had already closed); and the importer
  gained secondary-rate-limit backoff (`retry-after`-honoring, bounded, injectable clock) so a
  long import degrades to pacing instead of failing mid-run.
- **Issue-structure standard on the `file` path — BKL-2H9W + BKL-4C6P (2026-07-17):** a new
  deterministic `lib/backlog/issuefmt.py` (no model — INV-1) implementing
  `documentation/backlog-service-issue-standard.md`: `normalize_title` (§1 `area:`-prefixed
  atomic title, idempotent), `render_body` (§2 `### Section` composer — reserved for the MG6
  migration pre-pass, BKL-8N5K), and `lint` (§4 WARN-only, structured findings). Wired into
  `core.file_item`: title normalized on create, created issue audited, findings ride a dedicated
  top-level `lint` envelope field (distinct from operational `warnings[]`; never blocks, never
  touches the exit code — reusable as the migration audit). CLI prints `lint:` findings to
  stderr; api-contract §3 + standard §4 updated. Built from the design parent (issue-standard
  doc), not a build-plan chunk.
- **MG6 restructure pre-pass — BKL-8N5K (2026-07-17, Chunk 06 deliverable):** a new deterministic
  `lib/backlog/restructure.py` (INV-1) implementing issue-standard §5 "restructure, preserve, no
  split": fail-closed plan validation (a typo'd PFX or unknown key refuses the whole run before
  the data plane), application through the shared `issuefmt` composer (`normalize_title` +
  `render_body`, so a migrated body and a net-new one are layout-identical), verbatim `original_title`/
  `original_body` preservation as block fields (new `encode.format_text`/`parse_text` — JSON-string
  single-line encoding, fence-safe, recoverable byte-exact; Data Model §2), `kind:` backfill,
  non-atomic **flagging** (never auto-split — 1 PFX = 1 issue), and a WARN-only `issuefmt.lint`
  audit. CLI: `import --restructure <plan.json>` (plan applies **at create only** — skip-if-exists
  means an existing issue is never rewritten; the plan digest keys the checkpoint) + the offline
  `restructure-preview` op rendering the aggregate before/after owner-review artifact **from the
  same apply path the import consumes**. Build-plan MG1/MG6 reconciliation folded (Chunk 05 MIG-1
  note, Chunk 06 scrub flow, SPIKE-S2 settled-fact annotation); scrub runbook gains step 2b.
- **Chunk 06 must-fix BKL-8P2R — briefing/gate repoint, the safe way (2026-07-18):** the session
  briefing's backlog rollup is now **cutover-aware** on a new flat `backlog_service_repo:
  owner/repo` scalar in `project-state.yaml` (written by the migration session; API §2.4). Set:
  `briefing._backlog_pending_line` reads `snapshot.read` (file-only) with the **visible snapshot
  age**, then fires the **detached** `snapshot.spawn_refresh` warm — the never-block "few s"
  bound is **structural** (no synchronous network call exists on the briefing path; a stalled
  backend cannot reach it), which is how the item's timeout-scoping requirement is satisfied.
  Unset: the markdown parse is unchanged (MG3 coexistence). The three markdown-premise advisory
  probes retire on the same switch (`legacy-backlog-format`, `legacy-section-schema`,
  `backlog-overdue-grooming`); `external-backlog-detected` survives. The G2 never-block test
  injects a child whose `wait` **raises** (fire-and-forget pinned, not just fast-error) plus a
  wall-clock bound.
- **Pre-migration transport blockers BKL-2V6N + BKL-5T3J + redirect-follow BKL-5R2K
  (2026-07-18, from the holistic Fable review):** (1) `gh --paginate` emits each page as a
  SEPARATE JSON document, so `list_labels`/`list_timeline`/`list_sub_issues` hard-failed past one
  page — fatal mid-import once the repo crossed ~30 labels (216 aliases incoming), and every
  resume re-failed. Replaced with `transport._api_paged` (explicit `per_page`/`page` loop,
  raw-short-page terminator, bounded, injectable `per_page` for live spikes). (2) `list_issues`
  dropped PRs client-side, so every `len(batch) < per_page` terminator saw a filtered count and
  stopped scans early in PR-bearing repos — silently truncating `export` (the MG2 backup),
  `counts`, and the alias self-heal (a permanent-duplicate risk). The transport now returns raw
  pages; PRs leave the pipeline at `encode.is_prawduct_issue` (also rejects a mislabeled PR) with
  explicit `pull_request` guards on the label-keyed lookups (`_find_by_key`,
  `_numbers_for_alias`, `iter_alias_issues`). **Both live-verified read-only against the real
  target** (`brookstalley/prawduct`: 9 labels walked at per_page=3 set-identical; 128 raw
  entries / 122 PRs over 2 pages walked fully; the old filtered terminator demonstrably stopped
  at page 1 with 4 of 128). (3) BKL-5R2K: `get` now follows the `superseded_by` chain
  (`core.resolve_survivor`, shared with `migrate.resolve`) — the merged-away item is returned
  with `resolves_to` + a warning, human mode prints the survivor breadcrumb, and `pick` excludes
  an open-but-redirected item (the CRASH-2 window). Fake gains `seed_pull_requests`.

**Classification:** structural
## 2026-07-17: Test evidence meets real environments — false-red guard, fallback deprecation, multi-environment test_commands (fix)

<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Code + tests, no build plan (promoted
     TST-6F2R; precedent: the v3.0.2 declared-command-onramps fix). Governance-protected
     (bin/, test-status gate input) → full Critic. -->

**Parent:** TST-6F2R (upstream discodon report): with no `test_command` declared,
`test-evidence record` fell back to `sys.executable -m pytest` — the HOOK's interpreter — so a
venv-isolated product's suite died wholesale at collection and the hook persisted a
catastrophic false-red (discodon: 0 passed / 5074 failed) that polluted `test-status` and read
as a mass regression. Owner scope ruling (3.1.0): fix now, with first-class migration guidance
off the fallback, and make the declared path work reliably for multi-platform products (the
game shipping iOS + Android; the app with SQL + Python + React/Vite) — one product, several
test environments, one evidence record.

**What:**
- **False-red guard** (the report's load-bearing ask): an interpreter-fallback run with ZERO
  passes and only failures/errors — the wrong-interpreter signature — is **refused** (exit 2,
  nothing persisted) with migration guidance naming both declaration forms. Scoped to the
  fallback: a declared command is the operator's deliberate environment-aware invocation, so
  an all-red result there records honestly. The one carve-out from "a failing run is recorded,
  not dropped" — that contract's test now uses a mixed run (a pass proves the environment
  launched) and names the carve-out.
- **Fallback deprecated-by-nudge:** every fallback run prints a stderr note explaining the
  interpreter hazard and pointing at `test_command`/`test_commands`.
- **`test_commands:` — the multi-environment form** (`bin/prawduct-hook`, new
  `_read_str_list_yaml_key` block-sequence reader, stdlib-only): a list of canonical
  invocations, one per environment, each run under the existing declared-command rules (shlex
  list-form, mandatory `{junit_xml}`, no extra args) with its own JUnit report; counts
  aggregate across all reports into ONE record (the existing multi-`<testsuite>` summation,
  now spanning roots); any launch failure or unparseable report fails the whole record — no
  partial evidence. Mutually exclusive with `test_command:` (both declared = error); the
  ingest on-ramps (`--from-junit`, `--no-rerun`, `--from-counts` rejection) treat the list
  exactly as they treat the scalar. Exit status requires every command to exit 0.
- **Dogfooding:** prawduct's own `project-state.yaml` now declares
  `test_command: python3 -m pytest tests/ --junit-xml={junit_xml} -q` — the repo no longer
  rides the deprecated fallback it just guarded.
- **Critic fix round** (all warnings resolved in-branch): a declared-but-unparseable
  `test_commands` (flow style, nested mapping, empty) now REFUSES loudly instead of silently
  degrading to the fallback (new `_yaml_top_level_key_present` presence probe — the silent
  path could persist GREEN partial-environment evidence); full-line comments inside the block
  sequence no longer truncate the list; `--from-junit` is now **repeatable** so the ingest
  on-ramp scales with the list (one flag per report, aggregated, no-partial-evidence rules
  preserved); the record's `command` field joins with ` ; ` (no implied short-circuit); guard
  wording matches its condition (skips may accompany — the source incident had 35).
- Coverage: 12 new cases (`TestDeclaredCommandEnvironments`) — refusal persists nothing,
  fallback nudge, polyglot aggregation, honest red recording, both-keys error, per-command
  placeholder validation, launch-failure and unparseable-report no-partial-record, flow-style
  refusal, comment-tolerant lists, repeated `--from-junit` aggregation, `--from-counts`
  redirect. `methodology/building.md` Verify bullet, the record docstring, and
  `templates/project-state.yaml`'s TEST EXECUTION legend name the new knob; the
  cross-cutting-concerns coverage row updated. Follow-up filed: mixed JUnit/non-JUnit
  polyglots (`--from-counts` composition).

## 2026-07-17: Retrieval over generation — Principle 24 lands across the guidance surfaces (feature)

<!-- prawduct: type=feature | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Prose-only principle + methodology amendment,
     no build plan (promoted MET-4V8Q; precedent: audit batch / ambient-merge-commit).
     Governance-protected (CLAUDE.md, docs/principles.md, methodology/, skills/) → full Critic. -->

**Parent:** MET-4V8Q — user-directed incorporation of discodon's upstream learning candidate
(`prawduct-learning-retrieval-over-generation.md`): under momentum, builders substitute
generation (a fluent, plausible answer from prior knowledge) for retrieval (the cheap act of
grounding — a code read, a search, re-checking the artifact in hand). Days were lost tuning a
mechanism nobody had read when a 10-minute read + one search would have collapsed the effort.
Incorporated per Principle 19 (Evolving Principles), condensed to prawduct's voice — not
verbatim.

**What:** New **Principle 24 — Retrieval Over Generation** (Judgment) in `docs/principles.md`:
the cost-asymmetry mechanism (generation's short head / long tail vs. retrieval's bounded
cost), the cheap-check question ("what is the cheapest verification that could change this
decision — and did I do it?"), six condensed warning-sign detectors, and the cite-or-flag
rule; Skeptic review perspective gains "What cheap check hasn't been done?". Wired into the
operational surfaces so it binds where decisions actually happen: `CLAUDE.md` principles
roster (line 24); `methodology/building.md` Decision Research gains **the cheap-check gate**
(+ detectors) and Common Traps gains **"Tuning a mechanism you haven't read"**;
`methodology/discovery.md` Calibrate Rigor gains the cost-asymmetry gate ("mandatory, not
optional; notice when the asymmetry just went wide"); both session digests carry a
**Retrieval before generation** stance bullet (products get the full digest; this repo the
slim) and the full digest's Judgment roster gains the principle. Prawduct itself learns it:
rule + full narrative (incident, detectors) in `.prawduct/learnings.md` /
`learnings-detail.md`. Rider (release-scope item from the 3.1.0 review): `skills/onboard`
"Next: capture discovery" now names the **minimal-documentation path** — three cheap steps
(record characteristics, `coverage-scaffold --apply`, doctor "none to ratify") and the
coverage chain is permanently silent; prawduct is opinionated that absence be a recorded
decision, not that documentation be voluminous.

## 2026-07-17: templates/architecture.md — the seventh strategy-class artifact gets its authoring scaffold (feature)

<!-- prawduct: type=feature | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. One new template + registry reconciliation, no
     build plan (small additive work, promoted GOV-2T6K). Governance-protected (templates/) →
     full Critic. -->

**Parent:** GOV-2T6K — a product that records `multi_process_distributed` is triggered into an
architecture spec, but unlike every other strategy-class artifact there was no
`templates/architecture.md` to author from (the `coverage-scaffold` neutral stub covers the
coverage nudge, not the authoring path). Named a hard dependency of the structural-coverage
release line; included in 3.1.0 by owner scope decision.

**What:** Authored `templates/architecture.md` matching the sibling strategy-class templates'
structure: guidance-comment header (Tier 1; generated on `multi_process_distributed`; broad
surface definition — client+server, mobile+backend, services+workers, extension+host,
game client+authoritative server, host+plugins; proportionate-to-risk note; stub affordance
with the recorded-characteristic contradiction caveat), frontmatter (`depends_on`:
product-brief, data-model, security-model, nonfunctional-requirements), the audit-corrected
optional-Direction comment, and nine guidance-comment sections (Overview & Topology,
Components & Responsibilities, Communication & Boundaries, Data Ownership & Consistency,
Failure Modes & Resilience, Deployment & Version Skew, Scaling Model, Cross-Cutting Runtime
Concerns, Decision Log). Boundary-of-responsibility rule throughout: this artifact names the
topology; contracts point at api-contract/boundary-patterns, trust at security-model, targets
at nonfunctional-requirements. Reconciled `.prawduct/cross-cutting-concerns.md` (the "6 of 7"
row and the Known Gaps follow-up now record the gap closed).

## 2026-07-17: Ambient merge-commit default — the standing-instruction surfaces state the merge strategy (fix)

<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Small guidance-prose batch, no build plan
     (precedent: the release-audit batch). Governance-protected (CLAUDE.md, methodology/,
     skills/, templates/) → full Critic. -->

**Parent:** PR-8W3D (related WT-7M4K). The `/pr` skill's squash→merge-commit flip only binds
when `/prawduct:pr` runs; ad-hoc merges, worktree-exit integrations, and the moment `gh pr
merge --merge` fails on a squash-only repo are all unguided — and the model's training prior
(squash-and-merge as GitHub's dominant convention) fills that vacuum. Investigation confirmed
no harness/system-prompt instruction favors squash; the bias is a model prior at unguided
decision points, so the counter must be ambient (always in context), not skill-local.

**What:** Stated the merge-commit default on every standing-instruction surface: CLAUDE.md
Commit Conventions (new paragraph, parallel to the attribution rule — "overrides any harness
default to the contrary"); `methodology/session-digest.md` (product repos — bullet beside the
attribution bullet); `methodology/session-digest-slim.md` (deferral parenthetical updated;
also added the missing `norms` topic to its guide list — audit-batch coherence). Hardened
`skills/pr/SKILL.md` Merge Flow step 4: an absent preference means merge commit (a harness
default, GitHub UI default, or model inclination is not a preference); a failing `--merge` is
surfaced, **never** silently downgraded to `--squash`; a configured-squash branch is
single-use (delete after merge, never reuse) — plus an Important-section bullet. The
`templates/project-preferences.md` squash/rebase opt-in now carries the same single-use
branch contract. Discharges the guidance leg of WT-7M4K's residual (detection probes remain).

## 2026-07-17: Release-audit fixes — fleet-safe layer-0 delivery, adoption-scoped norm severity, template/doc corrections (fix)

<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Pre-release audit fix batch, no build plan
     (precedent: GOV-8R3F, WT-7M4K entries) — each fix is small and independently tested;
     governance-protected paths (lib/, bin/, skills/, templates/) → full Critic. -->

**Parent:** Pre-release audit of the held 3.0.6 line (2026-07-17, four independent review
passes + incoming-bugs cross-reference) found a cluster of defects sitting exactly where a
product-repo session meets the new norm-lifecycle/structural-coverage machinery — all
experiential, none crash-shaped; owner approved the fixes and the two design calls.

**What:**
- **Layer 0 (discovery-not-captured) is now an advisory-store probe** (`lib/coverage_probes.
  probe_discovery_not_captured`, warn priority) instead of a hard non-dismissible print in
  `cmd_clear` — dismissible per-clone via `/prawduct:advisory dismiss`, surfaced in the
  briefing's ADVISORIES block, staging against layer 1 unchanged (shared predicate, both
  probes now co-located). Owner call: visibility stays default-on; an owner who considers
  discovery settled can decline without editing state.
- **Critic norm-authority severity scoped to adoption** (`skills/critic/review-protocol.md`,
  canonical statement in `docs/norms.md` § Severity): norm departure/birth findings are
  BLOCKING only where ratified norms exist; in a norm-less product the same detections are
  **NOTE** (WARNING is treated as a de-facto blocker in practice) — a repo is never blocked
  into a lifecycle it hasn't adopted. Enforcement-table row updated to match, including the
  PR reviewer's WARNING layering (previously over-claimed as BLOCKING). Protocol addition
  paid for by in-block trims — the token-diet ceiling (3530) holds.
- **Structural scanner hardened** (`lib/coverage_probes.py`): indentation now tracked
  relative to the file's own levels (a 3-/4-space-reformatted state with a recorded
  characteristic no longer reads as unrecorded — which would have pinned the layer-0
  advisory permanently); `"0"` added to `_ABSENT_VALUES` (`exposes_programmatic_interface: 0`
  no longer wrongly requires an api-contract).
- **Advisory subsystem survives undecodable state** (`lib/advisory_store.load_project_state`):
  `UnicodeDecodeError` now caught alongside `OSError` — previously a non-UTF-8
  `project-state.yaml` killed the whole probe sync (hook path) or tracebacked
  `advisory show` (CLI path).
- **Wrong field name corrected**: `multi_party` → `has_multiple_party_types` in
  `docs/norms.md` (flip protocol ×2) and `skills/doctor/SKILL.md` #10 — a model executing
  the characteristic-flip protocol would have written a key no probe reads.
- **Template Direction footgun removed** (six strategy-class templates): the `## Direction`
  heading now lives *inside* the guidance comment (a kept empty heading read as ratified
  norms and started the perpetual 60-day sweep clock), and the instruction licensing a
  planning-time `norm_registry_ratified` write is replaced by routing "none to ratify"
  through the doctor's owner-confirmed Ratification Flow.
- **`docs/norms.md` reachable from product sessions**: new `norms` topic in
  `/prawduct:methodology`; all 18 bare `docs/norms.md` citations across digests,
  methodology guides, and skills replaced with the resolvable `/prawduct:methodology norms`.
- `coverage-status` docstring no longer claims "exactly one layer speaks" (layers 1+2 can
  both be active during partial authoring — matches docs and behavior).

Out of scope, tracked: `templates/architecture.md` (GOV-2T6K), TST-6F2R (false-red test
evidence — pending owner confirmation of approach).

Reconciliation with the "opt-out is a recorded artifact, not a suppression flag" learning:
the layer-0 dismissal is per-clone suppression by design — the *durable* opt-out remains
recording the characteristics (or their absence) in `project-state.yaml`; dismissal only
quiets the reminder in one clone, owner-approved as the lesser burden.

## 2026-07-17: SessionStart briefing no longer enumerates sibling worktrees (fix)

<!-- prawduct: type=fix | release=v3.0.5 | status=shipped -->

**Parent:** WT-8Q3N — the SessionStart briefing enumerated sibling worktrees as `- <branch> @
<path>`, which read as a menu of adoptable work and lured a session into working in a worktree it
did not launch in (colliding with that worktree's own live session). Root cause was briefing noise,
not a locking gap.

**What:** Removed the sibling-worktree enumeration from `lib/briefing.py`; the briefing now orients
the agent to its own worktree only ("work and gates are scoped to THIS worktree only; other
worktrees belong to their own sessions; do not read or modify them"). `_detect_worktrees` still
gates on >1 worktree and siblings remain discoverable via `git worktree list`. Regression test
added. Shipped as the v3.0.5 hotfix off v3.0.4 (b5d952c on main); this entry reconciles develop.

## 2026-07-17: Default PR merge strategy → merge commit (was squash) (fix)

<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Small behavioral default flip in skills/pr +
     template default; no build plan. Governance-protected (skills/) → full Critic + PR. -->

**Parent:** WT-7M4K — `/prawduct:pr`'s squash default erases each commit's identity on merge, so a
reused worktree branch keeps a *pre-squash* merge-base and every "what's new" computation
(SessionStart, `infer-critic-mode`/cumulative-Critic interval, `pr create`) over-counts
already-merged commits and re-reviews shipped code. Recurring in practice (discodon, prawduct v3.0.4).

**What:** Flipped the `/prawduct:pr` Merge Flow default from squash to **merge commit**
(`gh pr merge --merge`) in `skills/pr/SKILL.md`, and added an explicit `PR merge strategy: merge
commit` default row to `templates/project-preferences.md` so onboarded products inherit it visibly
and can still override (squash/rebase remain available — it's a preference, not a hard-code).
Merge-commit keeps a merged branch's commits reachable from the base, so its merge-base stays
correct and the gates stop over-counting. Reconciled this repo's own `project-preferences.md`
(the parenthetical no longer "overrides" a squash default — it now matches it) and rescoped WT-7M4K
to its residual (detection + post-merge hygiene for the squash-override and reused-branch cases;
severity medium-high → medium).

## 2026-07-17: Ratification seeds the Norm Health sweep baseline (fix)

<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Small read-side probe fix + tests +
     doc coherence. Governance-protected (skills/, lib/) → full Critic + PR. -->

**Parent:** surfaced by the norm-registry ratification (Layer 2) landing on develop — it cleared
`norm-registry-unratified` but immediately tripped `norm-health-sweep-overdue`, because that probe
keyed only off the janitor sweep stamp (absent on a fresh repo) while `## Direction` sections now
existed. Broke the repo-coupled tripwire `tests/test_norm_probes.py::TestSilentAgainstThisRepo`.

**What:** `probe_norm_health_sweep_overdue` now treats the effective "last full norm engagement" as
the **newer of the janitor sweep stamp and the ratification date** (`norm_registry_ratified`'s
leading date, via a new `_leading_date` helper that tolerates the fact's descriptive suffix).
Ratifying the registry is itself a deep pass over every norm, so a freshly-ratified repo isn't
flagged sweep-overdue until the 60-day window elapses — the nudge no longer fires the same day it
clears `norm-registry-unratified`. Re-baselined the repo-coupled tripwire to expect post-ratification
silence (re-fires on genuine drift: the ratification ageing past the window with no janitor sweep, a
`revisit:` expiring). Coherence: updated the probe docstring, the doctor SKILL step-5 contract (the
recorded value must lead with the date — it's now load-bearing), the test module docstring, and the
completed norm-lifecycle build plan's as-built note (its tripwire-must-fail claim is now superseded).
Filed COV-4H7N (the doc-only/state-only fast-paths let this break slip onto develop unseen).

## 2026-07-17: Ratify prawduct's norm registry — 20 Direction norms (norm-lifecycle Layer 2)

<!-- prawduct: type=docs | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Owner-ratified via the /prawduct:doctor
     surface-by-exception flow; governance-state + artifacts only, no code. -->

**Parent:** the norm-lifecycle Layer 2 close-out (`norm-registry-unratified` advisory) — the seven
strategy artifacts authored under GOV-5K3M were deliberately descriptive (no `## Direction`
sections), so the registry was unratified by design, handing the owner the ratification step. The
owner ruled on the decision-worthy candidates; the rest were bulk-confirmed.

**What:** Ratified 20 Direction norms across the strategy artifacts (statement + why + status per
`docs/norms.md` Anatomy):
- **data-model** (5): verdicts-from-facts / no-model-in-write-path (scoped to the Critic data plane),
  facts append-only, views never authoritative, schema-ahead surfaced, two-stores-two-lifetimes.
- **architecture** (4): reviewer-never-mutates-its-session, authority-closed / advice-soft,
  local-first (stdlib runtime), least-authority write boundary.
- **security-model** (2): untrusted-state-is-data, no-destructive-without-`--apply`.
- **api-contract** (3): `api_versioning_approach`, `api_error_model_approach`, additive-first.
- **observability-strategy** (2): severity-prefix + stdout/stderr split, single-writer ledger.
- **nonfunctional-requirements** (2): review-wall-clock-P0, state-file-thresholds-are-advisory.
- **operational-spec** (2): conservative versioning (judgment norm), gitflow develop/main.

**Owner rulings:** state-file thresholds ratified as **advisory** (warn/advise, no mechanical
enforcement — so over-threshold files are the nag's target, not violations, and no retroactivity
applies); verdicts-from-facts **scoped to the Critic data plane** (honest — test-run/PR-review
evidence is not yet on the store); conservative versioning bound as a **judgment** norm. Two wording
fixes applied (stdlib scoped to the runtime; the true least-authority write boundary). The
metrics/telemetry statement was left descriptive, not ratified.

Extended `project-preferences.md` § Enforcement into the product's norm index (added `Audit home` +
`Why` columns; 20 pointer rows). Recorded `norm_registry_ratified` in `project-state.yaml` — clears
the `norm-registry-unratified` advisory; `coverage-status` now reports the chain fully satisfied
(Layer 0/1/2).

## 2026-07-17: Norm-ratification flow surfaces by exception, not a flat wall (fix)

<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->
<!-- Statusless = release-pending once merged. Small prose/methodology fix, no build plan;
     Critic final 0 blocking / 0 warning after verify-resolutions. -->

**Parent:** GOV-8R3F — the doctor Norm Ratification Flow presented *all* candidate norms in one
flat block ("confirm-or-correct"). At scale (prawduct's own ratification surfaced ~20 candidates)
that becomes a wall the owner bounces off — or blanket-rubber-stamps, which silently defeats
owner-ratification, the exact failure the flow exists to prevent.

**What:** Rewrote `skills/doctor/SKILL.md` Norm Ratification steps 2-3 to *triage, then surface by
exception*. Step 2 tags each candidate **clear-to-ratify** (a decision plainly stands behind it,
statement matches the code today, why is obvious) vs **needs-a-ruling** (taxonomy: aspirational /
practice-not-written / wording-fork / collision / whyless). Step 3 presents asymmetrically —
needs-a-ruling individually with its fork + a recommendation, clear-to-ratify as one bulk-confirm
line — and **bans the flat dump above ~6 candidates**. Guard: bulk-confirm stays an *explicit*
confirm (silence ratifies nothing; no auto-ratification through the back door). Mirrored in
`docs/norms.md` § Adoption, with a cross-cutting learning captured (the pattern generalizes to any
owner confirm-or-correct batch). The sibling `skills/janitor/SKILL.md` Step-3 Reconcile shares the
shape — held out for scope discipline as GOV-8R3F's residual (`stage: ready`, a port of the shipped
taxonomy).

## 2026-07-16: Structural coverage — a forcing function for what a product owes (structural-coverage)

<!-- prawduct: type=feature | scope=structural-coverage | chunks=01,02,03,04,05 | release=v3.1.0 | status=shipped -->
<!-- Statusless on feature/structural-coverage = release-pending once merged. Large
     framework change, plan at .prawduct/artifacts/build-plan-structural-coverage.md,
     one commit per chunk, per-chunk Critic + closing cumulative (Chunk 05). -->

**Parent:** GOV-EXI2 — every framework mechanism is reactive (the Critic reviews diffs, the
sibling probes inspect existing files), so an artifact / structural characteristic / norm that was
*never created* is invisible to all of them (`[[reactive systems can't detect missing things]]`).

**What:** A three-layer coverage chain that keys off what a product *is* to require what it should
therefore *have*, staged so exactly one nudge fires at a time on the shared boundary predicate
`coverage_probes.structural_characteristics_recorded`. **Layer 0** (DISCOVERY-NOT-CAPTURED,
`bin/prawduct-hook`) — structural characteristics unrecorded; sharpened to fire on incomplete
`classification.structural` with product-definition work present, not only template-default nulls.
**Layer 1** (`lib/coverage_probes.py`) — the seven strategy-class artifacts: five universal
(data-model, security-model, nonfunctional-requirements, operational-spec, observability-strategy)
plus two characteristic-triggered (api-contract ← `exposes_programmatic_interface`, architecture ←
`multi_process_distributed`); coverage satisfied by the file EXISTING (a `(not relevant — <reason>)`
stub counts), single-homed in `missing_expected_artifacts` and shared by the probe, the
`coverage-status` doctor check, and the `coverage-scaffold` stub helper. **Layer 2**
(`norm-registry-unratified`) — retained, now proper staging behind layer 1. Doctor Health Check #11
+ routing row + two hook subcommands (`coverage-status`, `coverage-scaffold`);
discovery/planning/onboarding surfaces updated. GOV-EXI2 resolved by the upstream layer-1 owner (not
by ungating layer 2). GOV-5D2W fixed en route (empty-registry `advisory show` no-op, via
`lib/probe_families.register_all`). **Dogfooded on prawduct itself (Chunk 05):** recording
prawduct's six reconciled structural characteristics advanced the live chain layer 0 → layer 1,
naming all seven artifacts; the before/after transition is pinned by a fixture test decoupled from
live state (retiring an earlier repo-coupled zero-fire assertion). **Follow-up GOV-5K3M done in
this branch:** authored all seven strategy-class artifacts as real specs — grounded in the live
system (parallel research over the CLI surface, persisted formats, and process topology) and
written toward *intended* design, flagging target-vs-current divergence honestly — and recorded the
exposed-interface decisions (`design_decisions.api_versioning_approach` / `api_error_model_approach`
plus the flat `api_versioning_decided` resolution scalar) in `project-state.yaml`. Layer 1 now
clears and the chain advances to Layer 2 (norm ratification — owner-driven via `/prawduct:doctor`,
deliberately not auto-ratified). Remaining follow-up: GOV-2T6K (`templates/architecture.md`).

## 2026-07-16: Norm lifecycle — normative authority across governing artifacts (norm-lifecycle)

<!-- prawduct: type=feature | scope=norm-lifecycle | chunks=1,2,3,4,5,6 | release=v3.1.0 | status=shipped -->
<!-- Statusless on feature/norm-lifecycle = release-pending once merged. Large framework
     change, plan at .prawduct/artifacts/build-plan-norm-lifecycle.md (GOV-7Q4N), one
     commit per chunk, per-chunk Critic + closing cumulative. -->

**Parent:** GOV-7Q4N — a consuming product's telemetry-substrate divergence was laundered into
legitimacy through the doc-freshness pipeline (every reviewer executed instructions correctly;
the framework had no concept of a statement that *binds* future work).

**What:** Norms bind; descriptions track. Canonical spec at `docs/norms.md` (authority rule,
normative/descriptive test, lifecycle: birth/retroactivity, rulings, amendment, exceptions with
expiry, transitions, erosion/decay, characteristic flips; adoption path with the incident as
worked example). Enforcement consolidated into Critic Goal 4/3 + PR protocol + digests
(event-domain); five advisory probes in `lib/norm_probes.py` on machine-readable hooks only
(time-domain, cheap — incl. the two-arm `norm-registry-unratified`, gated on strategy-class
artifacts); janitor **Norm Health** theme with the re-affirm-or-retire fork + committed
`norm_health_last_run` stamp (time-domain, deep); doctor **Norm Ratification Flow** (owner
confirm-or-correct, additive writes, `norm_registry_ratified` shared answer) + registry-integrity
health check #10 (repair). Authoring: plan `governed_by:` seeded by `prawduct-hook jurisdiction`
(work-model index inversion), planning reconciliation dispositions, norm-birth tripwire in
building/discovery, `## Direction` blocks + Enforcement norm columns (Audit home / Why) across
templates; `/prawduct:learnings` surfaces Direction norms beside case-law rules. Backlog gains
`revisit:`. Follow-ups filed: GOV-6N4W (prompt classifier), JNT-8E3P (erosion metrics).

## 2026-07-14: Ephemeral-reference firewall — durable artifacts stay self-contained (ephemeral-ref-firewall)

<!-- prawduct: type=feature | release=v3.0.4 | status=shipped -->
<!-- Statusless on a feature branch = release-pending once merged. Medium framework
     change, no build plan (governance prose + one Critic check): a self-containment
     rule so ephemeral build identifiers (chunk labels, build-plan/work-cycle names)
     don't leak into durable product artifacts (code comments, long-lived specs). One
     final Critic. Owner-reported recurring leak; owner approved full-package scope. -->

**Parent:** Owner report (2026-07-14) — ephemeral identifiers ("chunk 03", "the eval-trust
build plan") recurring in durable artifacts (code comments, long-lived specs) where they mean
nothing after the build plan is deleted.

**What:** A firewall between build-cycle scaffolding and durable *product* artifacts. Build
plans and chunk labels are deleted when work ships (`/prawduct:pr`, janitor) and aren't unique
(every project has a "chunk 03"), so a durable artifact must never depend on one for its
meaning — comments carry the *why* inline. The distinction is product-artifact vs build-cycle
bookkeeping (change-log `chunks=`, backlog `closed-by:`, operator-verification, reflections,
PR/commit text legitimately cite chunks). Installed at: Principle 13 (Coherent Artifacts, using
Principle 10's construction-equipment metaphor); `methodology/building.md` builder rule;
`methodology/session-digest.md` (product-facing carrier); Critic Goal 4 (`ephemeral-ref
firewall` → WARNING). A deterministic grep tripwire was deliberately deferred (case-law-first; filed as `[GOV-3P8K]`).
## 2026-07-14: Stale remote-base diagnostics for the cumulative-critic gate (stale-remote-base-diagnostics)

<!-- prawduct: type=fix -->
<!-- Statusless on a feature branch = release-pending once merged. Medium
     framework fix, no build plan: a ~90-line shared git-inspection helper plus a
     reactive gate hint and a proactive session-start advisory across lib/coverage.py,
     lib/gates.py, a new lib/stale_base_probes.py, and bin/prawduct-hook; the backlog
     item's recorded fix-shape menu (fix-shapes #1 + #2) served as the plan. One
     final Critic. Closes COV-7K4N. -->

**Parent:** `[COV-7K4N]` (backlog) — false-`uncovered` with a misleading remedy when
`origin/<base>` is stale. Filed from the v3.0.3 release reflection (`learnings.md` /
`learnings-detail.md`: "reconcile a stale origin/<base> before re-reviewing"). Owner chose
fix-shapes #1 (near-term) + #2 (follow-up); fix-shape #3 (base-resolution re-architecture)
stays deferred — re-filed as `[COV-9B4T]` so the deferral stays trackable past COV-7K4N's close.

**Why:** `_resolve_base_branch` anchors the base to `origin/<b>` for a stable remote-tracking
merge-base. When local `<b>` carries release-prepped-but-unpushed commits (a "phantom release" —
a `release-prep(vX)` cut locally, never promoted/pushed) and a feature is built on that
ahead-state, `check_cumulative_critic` composes over `merge-base(origin/<b>, HEAD)` → HEAD and
drags the whole already-reviewed, already-shipped range into the required span — reporting
`uncovered` even though every commit carries a clean review fact (blocking=0). The code was never
unreviewed; the base pointer lagged. The stderr remedy ("run /prawduct:critic cumulative") is then
both wrong and expensive (~4–10 min re-review for zero signal); the actual fix is `git push origin
<b>`. Observed live during v3.0.3 (origin/develop at v3.0.1 behind an unpushed release-prep(v3.0.2)).

**What:** one shared detector plus the two fix-shapes that consume it.
- **Detector** (`coverage.diagnose_stale_remote_base`): returns a dict iff `base_ref` is
  `origin/<b>` and local `<b>` exists and is ahead of it — `{local, remote, commits_ahead,
  ancestor_of_head, release_prep_subject}`; `None` on every other shape (remote current, base not
  a remote ref, local branch absent) and on any git failure (never raises). `ancestor_of_head`
  separates the false-`uncovered` case (pushing moves the merge-base forward) from a diverged
  local branch (pushing wouldn't help).
- **Reactive (fix-shape #1)** — `check_cumulative_critic`'s `uncovered` path appends a NOTE when
  the base is stale *and* local `<b>` is an ancestor of HEAD: names the cheap `git push origin
  <b>` remedy (and the phantom release-prep) BEFORE the generic full-review fallback, converting
  the wrong first action into the right one. Purely additive text on an already-failing path — the
  verdict and exit code are unchanged.
- **Proactive (fix-shape #2)** — a new session-start advisory probe (`lib/stale_base_probes.py`,
  registered in `bin/prawduct-hook` `cmd_clear`) nudges *before* the gate is hit when local `<b>`
  carries an unpushed `release-prep(...)`. Release-prep-qualified (not merely "ahead of remote") to
  stay quiet during ordinary development; self-resolves on push (same observable state), like the
  gitignore/upstream probes. Evidence is count/version-independent so the advisory id is stable
  across the unpushed lifetime.

- `lib/coverage.py`: `diagnose_stale_remote_base` helper (colocated with `_resolve_base_branch`).
- `lib/gates.py`: the stale-base NOTE on `check_cumulative_critic`'s `uncovered` path.
- `lib/stale_base_probes.py` (new): the `unpromoted-release-prep` advisory probe.
- `lib/probe_families.py` (`register_all`): register the probe in the roster. (Written against
  `bin/prawduct-hook`'s inline registration block, which `GOV-5D2W` replaced with this shared
  composition root before the branch merged — re-homed at merge time.)
- `tests/test_stale_base_probes.py` (new): detector unit cases + probe fire/inert/self-resolve.
- `tests/test_cumulative_gate.py`: `TestStaleBaseHint` (hint fires; suppressed when remote current
  or local diverged). Full suite 1742 passed.

## 2026-07-14: Tree-validated test-evidence freshness (tree-validated-test-evidence)

<!-- prawduct: type=feature | release=v3.0.3 | status=shipped -->
<!-- Statusless on a feature branch = release-pending once merged. Medium framework
     feature, no build plan: an ~89-line additive clause across lib/gates.py +
     bin/prawduct-hook plus a validation matrix; the design spike served as the plan.
     One final Critic + a verify-resolutions delta pass. -->

**Parent:** `.prawduct/artifacts/spike-tree-validated-test-evidence.md` — the design spike for
kernel-v3 §4's deferred "test evidence on the store" item. Advances COV-3R9K suggested-fix-1 (the
ADDITIVE framing, distinct from the rejected replace-timestamp direction), closes the
governance-metadata false-re-run and the restart false-stale surfaced in the v3.0.2 session.

**Why:** test-evidence freshness (`tests_are_current`) keyed on the session timestamp (WHEN a run
happened), not the tree it ran against — so a restart with no change, a `.prawduct/*.yaml` edit,
or a doc-only edit all re-staled evidence and forced a full re-run. v3 tree-anchored REVIEW
evidence but left TEST evidence on the timestamp model.

**What:** an ADDITIVE tree-validity clause — `test-status` is current iff session-fresh OR the
judgeable-scoped working tree is byte-identical to the tree the recorded run ran against
(`evidence_tree`, captured via `evidence.capture_tree` at `record`; skipped for `--from-counts`).
A disjunction that only ever relaxes stale→current, so it is structurally incapable of the
false-STALE class that retired the content-hash fingerprint and `git_sha`. Classifies paths
(`is_judgeable_path`), never file contents. The env-drift tradeoff (the incidental per-session
re-run) was accepted by the owner. Validation matrix (§9): 11 relax/stale cases + 2
fail-toward-stale unit tests; full suite 1727 passed. Review protocols and `building.md` need no
prose change (they key off the `test-status` exit code).

- `lib/gates.py`: `_test_evidence_tree_valid` helper + the OR-clause in `tests_are_current`;
  `evidence_tree` optional-schema field.
- `bin/prawduct-hook` (`cmd_test_evidence`): capture the working-tree SHA; skipped for `--from-counts`.
- `tests/test_plugin_runtime.py`: `TestTreeValidatedFreshness` (matrix) + `TestTreeValidHelperFailsToStale` (fail-safe).
- Dropped the spike's proposed `head_tree` field (no consumer reads it).

## 2026-07-14: Test-evidence ingest on-ramps work with a declared test_command (test-evidence-declared-command-onramps)

<!-- prawduct: type=fix | release=v3.0.2 | status=shipped -->
<!-- Small bugfix, no build plan (a ~73-line CLI-validation relaxation across one
     hook, its docstring, one methodology bullet, and three tests — proportional
     effort warranted no plan, so no scope=/chunks=). Parent and provenance below. -->

**Parent:** `methodology/building.md` Verify bullet already promised the ingest on-ramps
(`--from-junit`, `--from-counts`, `--no-rerun`) as a universal way to record evidence *without*
re-running — completing the single-run intent of the `test-evidence-single-run` work
(COV-3R9K, `learnings.md`). The code contradicted that promise for the repos most likely to
need it. Surfaced by a v3.x product session: a declared-`test_command` repo ran its full
17,777-test suite, then was forced to re-run the *entire* suite through the hook just to stamp
evidence, because every cheap on-ramp was rejected when `test_command:` was set.

**Why:** `cmd_test_evidence` hard-rejected `--from-junit`, `--from-counts`, and `--no-rerun`
whenever `project-state.yaml` declared a `test_command:`. The exclusion assumed "if you declared
a runnable command, the hook can run it for you, so you don't need the on-ramps" — but the hook
re-running the declared command pays full-suite cost a *second* time, running the identical
command the builder just ran. So the products most likely to have large suites and to declare
their command were the only ones with no way to avoid a redundant full re-run.

**What:** Relaxed the exclusion, scoped by trust posture:
- **`--from-junit` + declared `test_command:` → allowed.** A declared command MUST emit JUnit
  (`{junit_xml}` is required), so ingesting the report the canonical command produced is honest,
  machine-backed evidence — the single-run path for a declared-command repo.
- **`--no-rerun` + declared `test_command:` → allowed.** Restamp reuses the existing record's
  counts and re-derives only the F4a coverage half; it introduces no new counts, so no
  scoped-subset risk.
- **`--from-counts` + declared `test_command:` → still rejected**, but the error now **redirects
  to `--from-junit`** (that command emits JUnit, so hand-typed counts — the one path with no
  artifact — are unnecessary and the weakest posture). This preserves the scoped-subset
  protection the knob exists for while fixing the discoverability half of the friction.
- The RUN-path constraints (`{junit_xml}` placeholder, extra-args rejection) are now gated behind
  a `will_run` flag so they apply only when the suite is actually run, not on ingest/restamp.
- Docstring + `methodology/building.md` Verify bullet updated to prescribe the declared-command
  single-run workflow.

**Tests:** `tests/test_plugin_runtime.py` — the from-junit rejection test became an
ingest-success test (a failing repo-test + passing ingested report → exit 0 proves the declared
command is not re-run); added a restamp-with-`test_command:` test; the from-counts test now
asserts the `--from-junit` redirect. Full suite green (1714 passed, 1 skipped, 0 failed).
Independent Critic review (final, single-pass): **0 blocking**, 1 warning (this change-log
entry), resolved here.

## 2026-07-14: Reviewers run on the session model — reviewer-model tiering removed (reviewer-session-model)

<!-- prawduct: type=fix | release=v3.0.1 | status=shipped -->
<!-- Emergency patch, no build plan (a prose/test change across three dispatch
     surfaces — proportional effort warranted no plan, so no scope=/chunks=). The
     removed mechanism is PAUSED, not deleted: rationale is retained in lib/risk.py,
     lib/telemetry.py, the A/B artifact, learnings, and backlog REL-5K8M for a
     planned restore. -->

**Parent:** User directive (2026-07-14): "prawduct is escalating to fable WAY too often …
remove anything about deciding what model to use. if the user is on opus, use opus; if the
user's on fable, use fable. don't try to switch intelligently." Reverses the reviewer-model
tiering shipped across v2.1.x (`build-plan-reviewer-model-tiering.md`,
`build-plan-reviewer-model-fallback.md`).

**Why:** Model choice lived entirely in skill *prose*, not code. Three surfaces mapped a diff
"tier" to a model: `skills/critic/SKILL.md` frontmatter pinned the coordinator to `model: opus`,
and both `skills/critic/review-protocol.md` and `skills/pr/SKILL.md` mapped `classify-diff-risk`'s
`escalate` verdict → `model: fable`. Because `escalate` fires for nearly any declared risk
surface (broad by design), reviews escalated to Fable constantly. The user wants no intelligent
switching — the reviewer should inherit whatever model the session runs on.

**What:** Removed all reviewer-model selection so reviewers run on the **session model**
(opus→opus, fable→fable):
- `skills/critic/SKILL.md` — dropped the `model: opus` frontmatter pin (the fork now inherits the session model).
- `skills/critic/review-protocol.md` — coordinator dispatches reviewers with no `model:` override (the `critic-reviewer` agent already declares `model: inherit`); `tier` is telemetry only.
- `skills/pr/SKILL.md` — PR reviewer dispatched with no `model:` override; removed the now-unused `classify-diff-risk` from Step 3 prose and allowed-tools.
- **Retained** (inert, for the planned restore): the `classify-diff-risk` command + `lib/risk.py`, the Critic `--tier` telemetry (pinned by `test_critic_consolidate.py`), and `review-stats` model-family aggregation. Model-recording plumbing still logs whatever ran.
- Doc-tail reconciled with PAUSED notes (Critic-flagged): `lib/risk.py` docstring, `lib/telemetry.py` comment, the A/B artifact, the pinned-alias learning (now dormant), and backlog REL-5K8M (paused pending restore).

**Tests:** `tests/preferences/test_reviewer_model_dispatch_prose.py` (renamed from
`test_risk_escalation_prose.py`) rewritten as regression pins — reviewer-dispatch prose must direct
the reviewer onto the session model and must not pin `model: fable`/`opus`/`sonnet`; the Critic
skill frontmatter must carry no `model:` override. Full suite green (1713 passed, 1 skipped).
Independent Critic review (final, coordinator — 3 reviewers on the **session model**, opus):
**0 blocking**, 3 warning, 5 note — all warnings/notes were coherence doc-tail + this change-log
entry, resolved above.

## 2026-07-13: Session-file .gitignore contract-drift advisory probe (kernel-evidence-store)

<!-- prawduct: type=feature | scope=kernel-evidence-store | release=v3.0.0 | status=shipped -->
<!-- Built alongside the kernel-evidence-store branch and ships under its scope
     (proportional effort: a ~100-line advisory probe warranted no build plan, so
     it has no chunks= of its own). Its own parent requirement and provenance are
     in the entry body below. Folding the release scope avoids the planless-scope
     regen-views blocker; the systemic fix (accept planless scopes) is backlogged. -->

**Parent:** `documentation/post-sync-advisory-spec.md` §1–2 (the advisory charter —
surface *this project should probably do X* nudges that self-resolve off a committed shared
fact). A fourth production probe under that mechanism, directly precedented by
`lib/upstream_probes.py` (trigger and resolution are the same observable state). Originated
from a prior-session review of the migration first-run experience: a plugin cannot start a
turn to reconcile a drifted `.gitignore`, but a session-start advisory lands the directive
in model context for the agent to act on at the first user turn.

**Why:** A product repo's `.gitignore` can drift from the framework's session-file contract
(`lib/core.py` `GITIGNORE_ENTRIES` / `RETIRED_GITIGNORE_ENTRIES` / `MANAGED_FILES`) — via a
prawduct upgrade that extended the contract, a fresh clone, a hand-edited `.gitignore`, or a
botched onboard. Session runtime files then get committed (cross-clone noise) or the tracked
build-plan gets ignored, and nothing surfaced it. Probing the *drifted state itself* is
strictly better than a version-delta banner line: cause-agnostic, persistent until fixed,
and zero per-release maintenance (the contract lives in code).

**What:** New `lib/gitignore_probes.py` registered in `bin/prawduct-hook` `cmd_clear`
alongside the existing probe roster. It fires an `info` advisory (`recommended_action:
prawduct-hook update-gitignore`, `/prawduct:doctor` as the alternative) when `.gitignore`
diverges, and self-resolves once reconciled — the committed `.gitignore` is itself the
shared answer store, so a teammate's fix resolves it for every clone on next sync (a
documented, reasoned deviation from spec §7.1's `project-state.yaml`-fact default). The fire
condition is EXACTLY `update_gitignore`'s `modified` condition: both read the new read-only
`lib.core.gitignore_contract_drift` (backed by a pure `_contract_diff`), so the nudge can
never outlive the fix. The hook never auto-edits the committed `.gitignore` (the no-noise
guarantee stays intact). Tests: `tests/test_gitignore_probes.py` (fire/inert/self-resolve,
count-independent evidence) + a fixer-parity and pairwise-disjointness guard in
`tests/test_gitignore_management.py`.

## 2026-07-13: Kernel v3 — shared evidence store; review gates answer by composition (kernel-evidence-store)

<!-- prawduct: chunks=01,02,03,04,05,06 | type=feature | scope=kernel-evidence-store | release=v3.0.0 | status=shipped -->

**Why:** The v2 review data plane kept evidence in single-slot, per-worktree files judged
by mode label and mtime — so a chunk-reviewed branch still demanded a redundant cumulative
re-review (CRT-J4PM), two predicates drew the metadata boundary differently and wedged the
gate with no exit (CRT-5D8Q), a perfectly good review went "stale" at every session
boundary, and worktrees couldn't see each other's evidence at all. Models also hand-wrote
protocol files, so one malformed write could silently lose a review.

**What:** Breaking release (gate attribution `since: 3.0.0`). Review evidence is now
append-only FACTS in a store shared by all worktrees of the clone
(`<git-common-dir>/prawduct/evidence.jsonl` — `lib/evidence.py`, D1–D3: tree-keyed capture
via a temporary index; schema-versioned envelope; idempotent appends). Gates answer by
composing facts over trees (`lib/coverage_algebra.py`, D6): the PR gate spans merge-base
tree → HEAD tree, the Stop gate spans session base tree → working tree — no mode labels,
no mtimes, no `extends_cumulative` chain bookkeeping. The review lifecycle is
code-written end to end (D8: `critic-begin` writes the dispatch manifest,
`critic-consolidate` appends the fact and regenerates `.critic-findings.json` as a derived
view no gate reads); models write only judgment partials. Prose surfaces (protocols,
methodology, digest) describe the composition data plane. Upgrade posture is zero-touch
(C9): the store initializes lazily so no consumer needs a migration commit, v2-era state
files are ignored with a block-with-remedy toward a fresh review, and schema-ahead facts
fail both gates closed with the update remedy. End-to-end scenario proof:
`tests/scenarios/test_kernel_v3_gate_cutover.py` (CRT-J4PM/CRT-5D8Q reproductions) +
`tests/scenarios/test_kernel_v3_upgrade.py` (upgrade posture, worktree + sequential-session
composition, discovery success criteria 1–4 trace in its module docstring). Chunk 06 also
swept the plan's vestiges: `lib/critic_mode.py`'s multi-link chain arm (stays-deleted
guards in `tests/test_critic_mode_inference.py`), dangling `TestChainAnchorParity`
references, and the orphaned `.critic-test-findings.json` gitignore line.

## 2026-07-10: Critic consolidation tolerates `files: []` on a finding (critic-empty-files-tolerance)

<!-- prawduct: chunks=01 | type=fix | scope=critic-empty-files-tolerance | release=v2.3.3 | status=shipped -->

**Why:** A downstream product (discodon) hit a hard `critic-consolidate` fail-close: one
reviewer partial carried a process/evidence finding with `"files": []`, and
`validate_partial` required a *non-empty* list whenever the key was present — so the whole
consolidation aborted and the gate kept reading the stale record. But `files: []` and an
*omitted* `files` key are semantically identical ("this finding isn't about a specific
file"), reviewers are only *told* to omit it, and a model naturally emits `[]`. Fail-closing
the entire review over a distinction that carries no meaning is exactly the silently-lost-review
failure class this module exists to prevent (follow-on to critic-persistence-redesign).

**What:**
- `lib/critic_consolidate.py` — new `_str_list` helper (a possibly-empty list of non-empty
  strings); `validate_partial` accepts an empty `files` list instead of requiring
  `_nonempty_str_list`. `[]` is normalized away downstream — `merge_findings` only keeps
  truthy files, so `[]` and omission produce byte-identical canonical records. The
  non-empty requirement is retained where it must hold (`goals`, `roster`, `files_reviewed`).
- `tests/test_critic_consolidate.py` — three regression tests: `files: []` accepted, a list
  containing an empty string still rejected, and `[]` normalized out of the canonical record.

## 2026-07-10: Single-PR bookkeeping — no post-merge commits on the integration branch (single-pr-bookkeeping)

<!-- prawduct: chunks=01,02 | type=fix | scope=single-pr-bookkeeping | release=v2.3.2 | status=shipped -->

**Why:** Consumers whose integration branches are protected (commits land only by PR) were
forced into a **second, bookkeeping-only PR** after every feature merge: the merge flow's
post-merge `stamp-merged` chore commit, trunk repos' `status=shipped` flips, and build-plan
retirement all required commits directly on the integration branch. Live report from a
product repo mid-build ("Want me to close out #1 and #2 in a small follow-up PR? It's the
only way to land those on protected develop"). The release-integrity value of REL-9F2T
never lived in the stamp — it lives in the `check-change-log-entry` probe, the "flip every
unreleased entry" release rule, and fail-closed regen validation, all retained.

**What:**
- **Chunk 01 (lib/hook):** a statusless *tagged* change-log entry is first-class
  release-pending state — `collect_release_pending_scopes` enumerates its scope (batched
  releases regenerate its plan with no stamp ever applied); the
  `diagnose_scope_plan_coverage` label stops implying a missed stamp; `stamp-merged` is
  deprecated (kept callable + convergent, announces deprecation on stderr).
- **Chunk 02 (flows):** `/prawduct:pr` create flow gains Step 1d — *the PR carries its own
  bookkeeping* (backlog archives, change-log status, derived views, trunk plan retirement
  all ride in the branch, atomic with the merge); merge-flow post-merge steps commit
  nothing (stamp step removed; missed bookkeeping folds into the next PR — never a
  housekeeping-only PR); `templates/change-log.md` rewritten (its status roster listed
  values regen-views treats as fatal, and it instructed post-merge stamping);
  release-process status model rewritten (statusless = expected release-pending; `merged` =
  accepted legacy); backlog-skill clause + planning.md cross-refs aligned; new guardrail
  test pins "no flow instructs a post-merge integration-branch commit".

## 2026-07-09: Critic persistence redesign — independent review that can't silently fail (critic-persistence-redesign)

<!-- prawduct: chunks=01,02,03,04,05 | type=fix | scope=critic-persistence-redesign | release=v2.3.1 | status=shipped -->

**Why:** Claude Code v2.1.198 (2026-07-01) flipped `Agent` subagents to background-by-default.
The Critic's `final`/`cumulative` coordinator is a `context: fork` skill that dispatched 3 review
subagents and **resumed inline** to persist (SKILL steps 7-8: write `.critic-findings.json` →
ledger anchor → `critic-end`). Under background-by-default the fork returns before that resume, so
the writeback never ran: the review was **silently lost** and surfaced later only as a
`check-cumulative-critic` deadlock (CRT-9K7T). A checkpoint placed *inside* the flow that fails
(the `critic-end` HEAD assertion) can't catch a flow that never reaches it.

**What (Option A — decouple model judgment from deterministic persistence):**
- **Chunk 01:** session-end backstop — `cmd_stop` blocks on a lingering `.critic-active` marker
  (the out-of-fork signal a review never persisted), read-only, deferring while background work is
  in flight. The guaranteed floor beneath every other mechanism.
- **Chunk 02:** `lib/critic_consolidate.py` + `prawduct-hook critic-consolidate` — reviewers write
  per-role partials; a deterministic, idempotent, fail-closed command merges them (union + dedup,
  highest severity) into `.critic-findings.json` + the ledger anchor, HEAD-coverage-checked, then
  clears the marker and removes the partials. No model in the write path.
- **Chunk 03:** `agents/critic-reviewer.md` (restricted tools bind the reviewer — CRT-3X9D becomes
  structural) + coordinator rewrite: write a manifest, dispatch the reviewers (they write only
  their partial), STOP — no resume-to-aggregate.
- **Chunk 04:** `SubagentStop` hook (matcher `critic-reviewer`) → `prawduct-hook subagent-stop`
  runs consolidation event-driven as each reviewer finishes; advisory (never blocks the subagent).
- **Chunk 05:** the backstop evolves from block-only to **consolidate-or-block** — complete
  partials self-heal (run consolidate), incomplete blocks naming the missing reviewer, marker-
  without-manifest blocks to re-run. Reconciled the coordinator prose (SKILL/review-protocol/
  review-cycle/CLAUDE.md) to the final flow.

**Independence is strengthened** (no model in the write path) and the findings/ledger schema is
unchanged, so downstream gates are untouched. Live validation of the harness firing the
SubagentStop hook + resolving the plugin `critic-reviewer` agent type is deferred to VRF-002 (it
can't be exercised until the plugin ships this branch). Closes CRT-9K7T; files CRT-4B7X
(consolidate concurrency double-ledger edge, low).

**Pre-merge hardening (post-review follow-ups):** `critic-begin` resets `.critic-partials/` so a
waived/stale-failed review's leftovers can't merge into a fresh dispatch at the same HEAD; builders
run `critic-consolidate` before reading findings after a coordinator review (SubagentStop becomes
latency-only, not correctness-bearing); per-role cross-check ownership wired (sustainability →
Learnings + Backlog, design → Framework-Specific Checks — the coordinator rewrite had orphaned
them); Gate 2a backstop messages made cause-neutral. Full suite 1606 passed.

## 2026-07-03: prose diet — reconcile, single-source, compress, fold (prose-diet)

<!-- prawduct: chunks=01,02,03 | type=improvement | scope=prose-diet | release=v2.3.0 | status=shipped -->

**Why:** Wave 1 Plan C of the owner-accepted efficiency-review fix program
(`framework-efficiency-review-2026-07-02.md`, MET-3Q8V, Overbuilt #3). The governance
cycle loaded ~28.5k words of prose that triplicated the mode×type matrix and the stance,
stated the final-mode fallback 5 ways, contradicted itself in 5 documented places, shipped
implementation narration (bug-ID citations, hook internals, a parser-bug story inside the
starter template), and compressed load-bearing rules into sentences weaker models can't parse.

**What:**
- **Chunk 01 (structural):** contradictions D1–D5 reconciled to read one way at every site
  (session-cap vs per-chunk review compose; PR readiness not PR action; one canonical
  fallback statement in `review-cycle.md`; reflection floor ≠ cadence, single explanation in
  `reflection.md`; discovery counts are "typical shape, not a quota"). D6 single-sourcing:
  `planning.md` canonical for mode/Type definitions, `review-cycle.md` keeps behavior tables
  only, template reduced to pointer + field syntax. `templates/build-plan.md` rewritten as a
  filled example ("Pantry", 2,774 → 1,197 words); parser-bug narrative removed.
- **Chunk 02 (compression):** the 8 cycle-load prose files rewritten for concision —
  narration, bug-ID citations, and bump-history deleted; Fable-ese de-compressed; every rule
  keeps exactly one clear statement. building.md token ratchet lowered 4950 → 4600; new
  `TestMethodologyProseHygiene` keeps bug-IDs/set-glyphs out of methodology files.
- **Chunk 03 (fold):** deleted `skills/{building,discovery,planning,reflection}/` and
  `methodology/agent-stance.md`; `/prawduct:methodology <topic>` is the single reader
  (absorbing the delegators' load-bearing lines); reference cascade across digests, skills,
  templates, bin/prawduct-hook ×5, lib ×2, README, MIGRATION, principles.md. Digest stance
  block rewritten advisor-first (STN-4W7R part a: expert take — risks, stronger/simpler
  alternative, recommendation — leads; compliance second), 239 words; slim synced.

**Measured outcome (estimator: words × 1.3):** cycle-load set 36,991 → 25,789 est tokens
(28,455 → 19,838 words), **−30.3%** vs the plan's ≥45% floor (40–45% honest-residue band).
**The floor is missed and, per the builder's and cumulative Critic's shared assessment,
cannot be met honestly.** Enumerated residue: (a) ~2.6k est tokens of verify-resolutions
chain / ledger / scope machinery inside the measured set whose diet is the explicitly
out-of-scope Overbuilt #4 item; (b) `review-protocol.md` (~3.2k) previously audited LEAN —
every bullet a severity-mapped check; (c) the behavior tables (mode×type matrix, demotion
table, per-mode scope) now single-sourced but irreducible; (d) the concrete anchors and
filled examples the plan's own Wave-3 thesis protects for weaker models; (e) the
no-dropped-rule hard constraint — the surviving corpus is predominantly single-statement
rules. Disposition: recorded as a vetoable outcome for the owner — amend the plan's Success
floor to the honest figure, or direct a further pass (realistic additional yield ~3-5
points, approaching rule-loss territory).

**Owner decision (2026-07-04): option (a).** The Success and Chunk-03 acceptance floors are
amended to the achieved **−30.3%**; the no-drop constraint held (no rule, gate semantic, or
checkable bar dropped). The ≥45%/50% target is recorded as a mispriced intuition — the
residue above is a measurement of rule density, not remaining waste. Chunk 03 marked `[x]`,
MET-3Q8V archived shipped.

**Classification:** governance

## 2026-07-02: fail-loud change-log tag validation + tolerant chunk IDs + regen-views --check (changelog-fail-loud)

<!-- prawduct: chunks=01 | type=feature | scope=changelog-fail-loud | release=v2.3.0 | status=shipped -->

**Why:** Wave 1 Plan B of the owner-accepted efficiency-review fix program
(`.prawduct/artifacts/framework-efficiency-review-2026-07-02.md`, VWS-6R4T, Overbuilt #2).
The change-log tag DSL's failures were partial and SILENT: a `chunks=` ID that didn't
literally match the plan's `Chunk <id>:` heading (zero-padding included) simply never
flipped, a `status=` typo passed with a warning nobody reads, and the documented release
pre-flight `regen-views --check` didn't exist. This class produced ~12 of this repo's 71
learnings and broke for trenchant's entire lifespan. The parent's "consider shrinking the
vocabulary" clause is descoped to REL-4Q9V (recorded HIGH-impact assumption in the plan).

**What:**
- `lib/views.py` — `normalize_chunk_id()` (case, `-`/`_`, numeric zero-padding) applied to
  BOTH sides of the checkbox flip; new `validate_chunk_roster()` (every `chunks=` ID on an
  entry whose `scope=` resolves to a plan file must match that plan's `## Status` roster —
  shipped entries included, since release-prep flips to shipped BEFORE regen runs); new
  `validate_tag_conflicts()` (conflicting scalars across tag lines split out of the
  multiplicity warning — first-wins may pick the wrong value).
- `bin/prawduct-hook` `cmd_regen_views` — validation is fail-CLOSED: any ERROR (status typo,
  roster miss, unreleased scope with no plan file, duplicate scope, tag-line conflict)
  exits 2 with NOTHING written; mere multi-tag-line union stays a WARNING. New `--check`
  flag: compute + validate + report, write nothing (exit 0 valid / 2 violations) — the
  release pre-flight two learnings already referenced.
- `docs/release-process.md` — step 4 opens with the `--check` pre-flight; the two
  warn-and-proceed sentences updated to the fail-closed contract.
- Tests: contract change documented — `TestRegenViewsStatusTypoWarning` (warn-and-proceed)
  rewritten as `TestRegenViewsStatusTypoError` (fail-closed), conflict clause moved from the
  multiplicity warning test to `TestValidateTagConflicts`; new lib + subprocess coverage for
  normalization, roster validation, fail-closed writes, and `--check`.

## 2026-07-02: work-model tripwire — maintenance-verb split + recursive doc corpus (gate-noise)

<!-- prawduct: chunks=01 | type=bugfix | scope=gate-noise | release=v2.3.0 | status=shipped -->

**Why:** Wave 1 Plan A of the owner-accepted efficiency-review fix program
(`.prawduct/artifacts/framework-efficiency-review-2026-07-02.md`, GOV-7T2M). The
undocumented-requirement tripwire counted maintenance verbs (refactor/rename/redesign/rework/
remove/replace) as requirement carriers, lowering the firing threshold to a single orphan on
routine-work prompts — it fired on the owner's own review prompt twice. Separately, the corpus
glob read only top-level `docs/`/`methodology/` markdown, so governing vocabulary in doc
subdirectories read as orphan sources. The item's other deliverable — pinning test-evidence
freshness to the `test-status` exit code in both review protocols — was verified **already
shipped** in PR #104 (2026-06-22, TST-4K2P) and descoped; the plan records the evidence.

**What:**
- `lib/work_model_index.py` — verb-set split: `REQUIREMENT_VERBS` drops the six maintenance
  verbs (they no longer make a prompt requirement-shaped); new `MAINTENANCE_VERBS` holds them,
  and `find_orphan_terms` exempts the union — a bare drop would have reported
  rename/redesign/rework (all above the frequency floor) as bogus orphan domain terms.
- `bin/prawduct-hook` `_work_model_corpus_paths` — `docs/`/`methodology/` globs go recursive
  (`rglob`). Safe in one direction only: extra corpus vocabulary can only suppress the nudge,
  never fire it. SessionStart force-rebuilds the index, so no staleness edge from
  newly-included old files.
- Tests: 4 new cases (maintenance prompts not requirement-shaped; single-orphan maintenance
  prompt silent; two-orphan maintenance prompt still fires; maintenance verbs never the
  orphan) + subdirectory coverage/staleness in the hook corpus tests. Live-hook before/after
  verified at the repo root: "refactor the noisiest gate" fired on old code, silent on new;
  "add the noisiest gate" still fires.
- Baseline repair ridden on this branch: added the missing v2.2.3 `CHANGELOG.md` public-digest
  entry (release-prep gap; `test_changelog_has_current_version_entry` failed on clean baseline).

## 2026-06-26: kill the test-evidence double-run at its source + a non-JUnit on-ramp (test-evidence-single-run)

<!-- prawduct: chunks=01,02,03 | type=feature | scope=test-evidence-single-run | release=v2.2.3 | status=shipped -->

**Why:** An upstream report (COV-3R9K, from scriob) said consumers run the suite twice per
chunk. A multi-agent investigation (a consumer map of every `.test-evidence.json` /
`changes_referenced` reader, empirical `git diff` traces in throwaway repos, the
TST-4K2P/TST-7M3K history, and three adversarial verifiers) found the double-run is **not**
gate-forced: freshness is session-scoped (`lib/gates.py:tests_are_current` compares `timestamp`
to `.session-start` — no `git_sha`/HEAD/tree-hash since TST-4K2P), and `changes_referenced` is
produced by `git diff --name-only <base>` (base→**working tree**, content-based) — commit-invariant
on a real base branch. The report's cited `git diff base...HEAD` membership-shift was a
misdiagnosis. The real cause is a **retired** "record AFTER the final commit / SHA must equal HEAD"
habit (declared obsolete at `learnings.md:270-272`) that outlived the `git_sha` it papered over.
The investigation also surfaced an **agnosticism gap**: the recorder is JUnit-XML-coupled (default
pytest, `test_command:` requires `{junit_xml}`, `--from-junit` ingests JUnit), so a non-JUnit
toolchain (embedded HIL, a bespoke harness) had no first-class on-ramp — counter to Prawduct's
language/platform-agnostic stance.

**What:**
- **`--from-counts passed=N failed=M skipped=K [duration=S]`** (`bin/prawduct-hook` `cmd_test_evidence`)
  — record pass/fail/skip counts supplied directly, the language-/runner-agnostic on-ramp for any
  toolchain that can't emit JUnit XML. Runs nothing; rejects a second source.
- **`--no-rerun` (alias `--restamp`)** — reuse the existing record's counts and refresh the
  `timestamp` + F4a coverage half against the current tree, with no suite run. The cheap refresh
  after a rename / force-add shifted `changes_referenced` (the two real coverage-half shifts an
  adversarial verifier confirmed). Trust posture matches `--from-junit`; **no** content/tree-hash.
- **HEAD~1 fallback-base advisory** — the recorder and the standalone `bin/test-reference-verify`
  warn (naming `base_branch:`) when the diff base resolves to the moving `HEAD~1` fallback, the one
  path where a no-op commit genuinely shifts the changed-file set. Advisory only; resolution unchanged.
- **`methodology/building.md`** — the Verify *Code:* bullet now prescribes recording **once, at
  Verify, not after committing** (a commit doesn't stale session-scoped evidence; `test-status` stays
  green), and names the mechanism-neutral on-ramps. Two duplicated "no pre-existing exception"
  clauses were trimmed to offset the addition (the <4950-token cap held — no bump).
- **Backlog** — COV-3R9K reframed with the verified diagnosis and closed; the stale "record after
  commit" stopgap in the TST-4K2P content-hash item marked **SUPERSEDED**; new **COV-4M2J** filed for
  the Python-only coverage floor (the bring-your-own-verifier escape is the current workaround).
- **Deliberately NOT done:** content-/tree-hash or `git_sha`/HEAD freshness (removed pre-v1.4 for
  chronic false positives; TST-4K2P explicitly rejected re-adding it). Freshness stays session-scoped.

## 2026-06-25: work-model vocabulary index is now gitignored in product repos (work-model-index-gitignore)

<!-- prawduct: chunks=01 | type=bugfix | scope=work-model-index-gitignore | release=v2.2.2 | status=shipped -->

**Why:** The work-model feature (PR #71) generates a derived vocabulary index at
`.prawduct/.work-model-index.json` on every session (the SessionStart `build-index` hook and the
UserPromptSubmit `user-prompt-submit` hook, both gated only on `.prawduct/` existing — so it fires
in *every* governed repo). It was always meant to be ephemeral/gitignored, and PR #71 added the
ignore line to *this framework repo's own* `.gitignore` — but never to the canonical contract that
propagates to product repos. So onboarded products generated the file every session with no ignore
rule for it, carrying it as permanent untracked noise. The original test
(`test_index_is_gitignored`) only checked this repo's hand-edited `.gitignore`, so it passed while
the real propagation gap went uncaught.

**What:**
- **Add the entry to both contract lists** — `lib/core.py::GITIGNORE_ENTRIES` (what
  `update_gitignore` writes into product `.gitignore` files on onboard/doctor) and the import-light
  inline mirror `bin/prawduct-hook::_SESSION_GITIGNORED_PATHS` (the `_untrack_session_files`
  un-track set). `TestSessionGitignoreMirror` already pins the two in sync.
- **Self-heal for existing products** — `update_gitignore` adds the missing line on the next
  session, and once it is in `_SESSION_GITIGNORED_PATHS` any repo that already committed the file by
  accident gets it `git rm --cached` by `_untrack_session_files`.
- **Strengthen the regression net** — `tests/test_work_model_hooks.py` gains
  `test_index_is_in_gitignore_contract` (asserts the contract list, not just this repo's
  `.gitignore`) and `test_update_gitignore_writes_index_line` (end-to-end: a freshly reconciled
  product `.gitignore` ignores the index).

## 2026-06-25: Stop hook defers session-end gates while harness-tracked background work is in flight (stop-gate-defer)

<!-- prawduct: chunks=01 | type=bugfix | scope=stop-gate-defer | release=v2.2.2 | status=shipped -->

**Why:** A coordinating agent that launches a background `Workflow`/`Task` and yields trips the
Stop-hook Critic/reflection gate on every turn (`files changed, no Critic yet`) — but the diff isn't
final and the session *can't* end (the harness re-wakes it when the job lands), so each block is pure
noise. One reported session absorbed ~15 block-loops over a ~12-min lane (`STH-3W7F`). The
2026-06-04 investigation ruled out auto-detection because the Stop hook could not then see live
jobs; that premise is now obsolete — Claude Code puts a `background_tasks` array on the Stop event
(v2.1.145+; verified against installed 2.1.191).

**What:**
- **Auto-detect, don't self-declare** — the Stop hook reads its stdin payload
  (`bin/prawduct-hook::_read_stop_stdin`, fail-soft) and, via the pure decision helper
  `lib/gates.py::background_tasks_in_flight`, defers the session-end blockers when harness-tracked
  work is in flight: `cmd_stop` returns 0 with a `GATES DEFERRED` note (and skips the `gh pr list`
  probe) instead of exit 2. This supersedes the half-designed self-declared `.gates-deferred` marker
  (STH-3W7F option b) — auto-detect needs no agent action and can't drift or be abused.
- **Defer, never skip** — the deferral is stateless (recomputed from the live array every Stop), so
  it re-arms the instant `background_tasks` empties; the Critic/reflection still fire when the work
  lands. This is fixing the in-flight *classification*, not demoting a blocker to an ignorable
  warning.
- **Degradation ladder keeps the gate sound** — `background_tasks` absent (older client / registry
  unreachable / no stdin), empty (idle), or malformed all fall to the existing blocking behavior;
  only a clearly-present non-empty list defers. Untrackable external waits (CI, a remote queue) leave
  the array empty and still block (the STH-3W7F option-d TTL escape hatch is deferred as a separate item).
- **Docs + tests** — `methodology/building.md`'s in-flight floor now describes the shipped
  auto-defer; `tests/test_stop_gate_defer.py` (new) unit-tests the full ladder, and
  `tests/test_plugin_runtime.py` gains a `stdin=` param + end-to-end defer / block / re-arm /
  no-regression cases.

## 2026-06-24: regen-views no longer aborts when no build plan resolves; YAML-null pointer reads as unset (regen-views-null-plan)

<!-- prawduct: chunks=01 | type=bugfix | scope=regen-views-null-plan | status=shipped | release=v2.2.1 -->

**Why:** On a clean release boundary — change-log carries `release=`/`status=shipped` entries but
no build plan resolves and `active_build_plan` is `null`/unset — `prawduct-hook regen-views` raised
`FileNotFoundError: build-plan not found at .prawduct/null` and exited 2 **before** regenerating the
plan-independent `release-notes.md` and `scope_rollups`, blocking `docs/release-process.md` step 3.
Reported twice upstream from the Hallucinote repo (v1.6.0, then v1.6.1 after it recurred) and live in
this repo too (the SessionStart briefing fired `'null' resolved to .prawduct/null`). Two layers
(`VWS-7N3K`): the column-0 pointer reader treated the YAML `null` literal as the truthy string
`"null"` (resolving to the phantom `.prawduct/null`), and `_plan_status_results` raised on *any*
unresolved plan rather than treating "no active plan" as a legitimate no-op under the multi-scope
model (`REL-4T8N`).

**What:**
- **Normalize the YAML null literal at the pointer reader** — `lib/core.py::read_str_yaml_key` (and
  its parity-pinned inline mirror `bin/prawduct-hook::_read_str_yaml_key`) now read `null` / `~`
  (case-insensitive) / empty as `None`, mirroring the opt-out
  `lib/views.py::_parse_build_plan_frontmatter_scope` already honors for `scope:`. `active_build_plan:
  null` now resolves to the default plan (not `.prawduct/null`), and the STH-5P2W briefing guard no
  longer mis-fires on the canonical "no active plan" opt-out.
- **Degrade gracefully when no plan resolves** — `lib/views.py::_plan_status_results` returns no
  status results (a no-op) instead of raising when `plan_paths` is empty AND the pointer is
  unset/null, so `plan_regen` still regenerates release-notes + scope-rollups. The loud
  `FileNotFoundError` is preserved for a genuine misconfiguration: an *explicitly-pinned*
  `active_build_plan` that resolves to a missing file.
- **Tests** — null/`~` normalization + resolver fallback + hook-mirror parity
  (`tests/test_build_plan_resolution.py`); zero-plan graceful-degrade vs. pinned-missing-raises at
  both the `plan_regen` and `regen-views` command levels (`tests/test_views.py`); briefing no longer
  warns on `active_build_plan: null` (`tests/test_briefing_functions.py`). The prior
  `test_missing_build_plan_returns_nonzero` (which pinned the buggy abort-on-absent-plan contract)
  was split into the corrected `test_unset_pointer_missing_plan_returns_zero_and_regenerates_views`
  and the preserved `test_pinned_missing_plan_returns_nonzero`.

## 2026-06-24: doctor↔janitor scope boundary — canonical split + mirrored skill summaries (doctor-janitor)

<!-- prawduct: chunks=01 | type=feature | release=v2.2.0 | scope=doctor-janitor | status=shipped -->

**Why:** The api-design work landed the new API-versioning concern in BOTH a `/prawduct:doctor`
check (#9) and a `/prawduct:janitor` theme, exposing that the line between the two "health check"
skills was never written down (`GOV-9K2T`). Nothing told a maintainer which skill a new concern
belongs to, so the next cross-cutting concern would reopen the same question.

**What:**
- **NEW `docs/doctor-vs-janitor.md`** — the canonical boundary: the three-axis split (subject /
  action-model / question-type), the placement rule for a new concern, the "legitimately both"
  pattern (API versioning, gitignore) and the handoff adjacencies (Template Currency, backlog).
- **Mirrored `## Scope & boundary` summaries** in `skills/doctor/SKILL.md` (governance/install
  conformance — reports & guides) and `skills/janitor/SKILL.md` (the product's own codebase craft —
  surveys & fixes), each pointing to the canonical doc.
- **gitignore cross-reference** added in both directions — doctor #8 (prawduct contract) ↔ janitor
  Version Control Hygiene (general hygiene) — the one shared concern that wasn't previously linked.
- **Methodology index** (`skills/methodology/SKILL.md`) now places both maintenance/health skills
  on the governance map (it previously named only critic/pr/learnings/backlog).
- **NEW `tests/test_doctor_janitor_boundary.py`** — structural guard locking the three-place
  coherence (canonical doc exists; both skills carry the summary, the pointer, and the gitignore
  cross-ref; the index lists both). No checks were added, removed, or moved — the API check stays
  in both skills with its two facets delineated.

## 2026-06-24: API design (produced) — pipeline coverage for the product's own exposed-API decisions (api-design)

<!-- prawduct: chunks=01,02,03,04,05,06 | type=feature | release=v2.2.0 | scope=api-design | status=shipped -->

**Why:** The framework's largest uncovered cross-cutting concern was the
product's OWN exposed API. "Versioning" appeared exactly once (discovery.md:15,
one word in a list) and was dropped at every downstream stage — no artifact
template, no builder guidance, no Critic check, no matrix row (the consumed-side
"Foreign API verification" row is a different concern). The motivating product
(../scriob) ran unversioned for ~697/700 commits on an unchallenged one-word
deferral, then paid a coordinated breaking-change retrofit when a deploy forced
the issue. Design stance (user-confirmed): **force the decision, don't mandate
the answer** — WARNING-severity / dismissable, "none — internal-only" is a valid
recorded decision, a deferral must be dated with a revisit trigger.

**What:**
- **Chunk 01 (keystone):** `templates/project-state.yaml` decision-record schema
  (`design_decisions.api_versioning_approach` + `api_error_model_approach`;
  commented-out top-level `api_versioning_decided` answer-store fact) + discovery
  (`discovery.md`:15) / planning (`planning.md`:29) capture points.
- **Chunk 02:** new `templates/api-contract.md` (transport-neutral — network /
  library-SDK / on-device / CLI, not HTTP-only) + planning "Exposed API" section
  + build-plan `**Exposed API:**` field + guard tests.
- **Chunk 03:** Critic Goal-2 **Exposed API** bullet (`review-protocol.md`) —
  recorded versioning + error-model decision (or dated deferral) → WARNING each.
- **Chunk 04:** retroactive detection — doctor health check #9 + a janitor
  "API Design & Versioning Hygiene" theme (survey, not gate) + `api` shorthand.
- **Chunk 05 (code):** `lib/api_versioning_probes.py` — an `info`/dismissable
  post-sync advisory firing when an exposed API is detected but no decision is
  recorded; polyglot detection (Python imports, JS/Go/Java manifests, openapi/
  swagger/proto/graphql) via a new skip-dir-aware `Codebase.has_source_matching`.
- **Chunk 06 (coherence/close):** cross-cutting-concerns "API design (produced)"
  row + Known-Gaps; OWASP API Top 10 *design*-failure prompt (BOLA, mass
  assignment, excessive data exposure) in security-model + discovery; two
  learnings captured.
- Deferred follow-ups filed: CRT-4Q7K (coded auto-detect Exposed-API trigger),
  TPL-8H3M (standalone error-model template). 17 new tests; 1428 green.

## 2026-06-22: Test-evidence `record` cluster — retire the misleading git_sha, ingest existing JUnit runs, loud-fail on empty discovery (test-evidence)

<!-- prawduct: chunks=01,02,03 | type=feature | release=v2.1.8 | status=shipped | scope=test-evidence -->

**Why:** Three independent fixes on the `test-evidence record` surface, bundled
into one PR for review economy (a code survey confirmed they share the surface,
not an abstraction). (1) The record carried a `git_sha` field that **no runtime
code reads** and that is **not** in the evidence schema — its only live effect
was the PR-reviewer eyeballing it and emitting false-positive "stale" warnings.
Freshness is timestamp-based via `prawduct-hook test-status`; content-fingerprinting
was deliberately removed pre-v1.4 after chronic false positives, so the backlog's
"re-introduce content-hashing" premise was wrong. (2) `record` re-ran the whole
suite even when the builder had just run it — a double-execution of the test
suite. (3) When test discovery found zero files (e.g. a monorepo without the
`tests_dirs:` knob set), `record` wrote empty `changes_referenced`/`tests_executed`
halves **silently**, reading downstream as false missing-coverage.

**What:**
- **Chunk 01 (TST-4K2P):** Removed `git_sha` from the record and dropped the
  `git rev-parse HEAD` call that fed it. Retargeted the PR and Critic review
  protocols to determine freshness **only** via `prawduct-hook test-status` —
  never inferring staleness from a commit/SHA field. Replaced the now-obsolete
  "record test-evidence after committing" learning (the timing workaround existed
  only for the removed field).
- **Chunk 02 (TST-7M3K):** Added `record --from-junit <path>` to ingest a JUnit
  XML the builder already produced instead of re-running the suite (default
  behavior unchanged; `--from-junit` combined with `test_command:`/trailing
  pytest args is rejected as a conflicting source). Documented the single-run
  Verify flow in `methodology/building.md`.
- **Chunk 03 (TST-2H9P):** `bin/test-reference-verify` now fails **loud** when
  zero tests are discovered while judgeable files changed (naming the `tests_dirs:`
  knob) instead of writing empty halves silently, and `record` now forwards the
  previously-swallowed verifier stderr.
- 10 new tests; 1368 green.

## 2026-06-22: Raise the Critic review-protocol.md token budget 3120 → 3350 — relieve an operationally-zero ceiling without abandoning the trim discipline (critic-protocol-budget)

<!-- prawduct: chunks=01 | type=refactor | release=v2.1.8 | status=shipped | scope=critic-protocol-budget -->

**Why:** `skills/critic/review-protocol.md` had reached 3116 of its 3120-token
test ceiling — 4 tokens of headroom, an operational zero that forces a harmful
trim on the *next* legitimate check. An audit found the file LEAN, not bloated:
every goal bullet is a specific, severity-mapped check, already compressed across
many documented passes. The one relocatable block (the findings-JSON field
glossary) is genuinely useful inline next to its template, so relocating it purely
to clear the number would fragment the instructions — the anti-pattern the budget
exists to prevent. And the ceiling is only ~1-2% of a medium/large review's token
cost (the file loads into a 4-10 min opus review over a full diff + 3 subagents),
so it is an anti-bloat **discipline** knob, not a material cost control.

**What:** Raised the ceiling to 3350 (+230 tokens ≈ room for 3-4 future checks)
in `tests/test_v5_methodology.py`, with the rationale recorded in the test
comment. The discipline posture is **unchanged** — the comment still mandates
"prefer trim over bump, and relocate per-mode/record detail to `review-cycle.md`
before adding here." No protocol content changed; this is purely the test
threshold. Part of the review-streamlining track (alongside the telemetry
model-id fix and the PR-reviewer single-owner scoping).

## 2026-06-22: Single-owner the PR reviewer's Learnings Cross-Check & Backlog R-1 — scope them to the consumed Critic record (single-owner-shared-checks)

<!-- prawduct: chunks=01 | type=refactor | release=v2.1.8 | status=shipped | scope=single-owner-shared-checks -->

**Why:** After the consume-and-audit redesign (the PR reviewer audits the Critic
record instead of re-deriving code soundness), the PR reviewer *still* re-ran two
checks the cumulative Critic already does over the same diff: the Learnings
Cross-Check and the Backlog "resolved items" walk (R-1) — duplicated scanning
across two agents. B0 (the validate-first step of CRT-5T8N) confirmed this is
*true* duplication, not complementary work, but found the naive fix ("just delete
it from the PR reviewer") has a **coverage gap**: the PR gate can be satisfied by
a `verify-resolutions` **chain record**, which runs Goals 1-3 only and never runs
those cross-checks over its delta `<anchor>...HEAD`. The PR reviewer's own scan
was the only thing covering that delta.

**What:** The PR reviewer's **Learnings Cross-Check** and **Backlog R-1** are now
scoped to the consumed record — skip on a HEAD-covering `cumulative`/`final` (the
Critic owns the bundle scan; rely on the audited record), scan **only** the
chain-delta `<extends_cumulative.commit_reviewed>...HEAD` on a `verify-resolutions`
record (closes the gap), full scan on a voided/absent record (the pre-scoping
behavior). **R-2** (change-log↔backlog data inconsistency) stays unconditional —
the Critic does not do it. `skills/critic/review-cycle.md` names `final`/`cumulative`
as the explicit **owner** of both cross-checks so the division reads from both
sides. 2 guard tests added (`tests/test_pr_reviewer.py`). Cuts duplicated reviewer
work without losing assurance (CRT-5T8N, the B item of the review-streamlining
track). *Note:* the item assumed the Critic-side detail lived in
`critic/review-protocol.md`; it's actually in `review-cycle.md` (review-protocol.md
only references it), so the ownership statement landed there.

## 2026-06-22: Fold reviewer model-id aliases to a family label in review-stats so the model dimension isn't fragmented (telemetry-model-id-normalization)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.8 | status=shipped | scope=telemetry-model-id-normalization -->

**Why:** `review-stats` groups reviews by role × model × mode, but one model is
recorded under several id strings (`opus`, `claude-opus-4-8`,
`claude-opus-4-8[1m]` are all the same model), so it split that model across
three buckets — the 2026-06-22 run fragmented critic-opus reviews across
`opus` / `claude-opus-4-8` / `claude-opus-4-8[1m]`, making per-model yield
unreadable and defeating the reviewer-model A/B the dimension exists to answer.
Surfaced while mining review-stats for the evidence-driven review-pruning track
(**TEL-4M9X**, the first deliverable of that track).

**What:** A `_canonical_model` helper folds a recorded id to its Claude family
(`opus`/`sonnet`/`haiku`/`fable`) at the aggregation key only — `fable`/`sonnet`
stay distinct from `opus`, and an unfamiliar id passes through verbatim (never
bucketed under a known family). Substring match, so a future model *version*
folds with no code change (the drift-resilience the reviewer-model fallback
chains chose over pinned ids). The raw id stays untouched in each append-only
ledger line, so the historical 41 events aggregate correctly with **no rewrite**
— a read-time view. Folds **values, not keys**, so `REPORT_SCHEMA_VERSION` holds.
4 tests added; `docs/governance-telemetry.md` documents the fold.

## 2026-06-21: Batch git subprocess fan-out on the SessionStart/Stop hot paths (hot-path-git-batching)

<!-- prawduct: chunks=01 | type=refactor | release=v2.1.8 | status=shipped | scope=hot-path-git-batching -->

**Why:** The `clear` (SessionStart) and `stop` (Stop) hooks spawned more git
subprocesses than needed — measured 25 on `clear`, dominated by
`_untrack_session_files` issuing one `git ls-files --error-unmatch` per session
path (15), plus `git status --porcelain` re-run by each baseline-diff probe (3 on
`clear`, 2–3 on `stop`). On a monorepo each git invocation is dominated by
repo-scan latency, so the fan-out risks multi-second session-start stalls.
`_has_product_code` compounded it by walking the entire tree (including a large
`node_modules`) before its filter discarded those paths — and that path fires
exactly when a JS repo is being onboarded. From the 2026-06-09 framework review
(STH-6Q9D).

**What:** Three behavior-preserving optimizations on the shared hot-path surface.
(1) `_untrack_session_files` learns the tracked session-file set in ONE
`git ls-files -z -- <paths>` and untracks in ONE `git rm --cached` (was 15 + N) —
`clear` drops 25 → 11 git subprocesses. (2) The status-family probes
(`git_has_changes`, `git_has_session_changes`, `_session_changes_are_doc_only`,
`git_has_code_changes`, `_get_session_changed_files`) gained an optional
`status_output=` parameter so a hot-path caller captures `git status --porcelain`
once and threads it down; applied at the two dense callers —
`_check_previous_session_gates` (3 → 1 on a dirty session) and the `cmd_stop`
preamble (3 → 2 on a session with changes). Default `None` preserves every
existing caller. (3) `_has_product_code` prunes `node_modules`/`.git`/`.prawduct`
at the directory level via `os.walk` and short-circuits on the first product-code
file — same verdict, no full-tree enumeration. The remaining
`git branch --show-current` ×4 on `clear` is a cross-function thread, filed as
STH-3K7M. New `tests/test_hot_path_git_batching.py` pins the batched-call counts,
the capture-once contract (passed snapshot is not recomputed), and the prune
contract (`node_modules` never enumerated); behavior-preservation tests guard each
deliverable. Full suite 1365 pass / 0 fail.

## 2026-06-21: Hook-CLI robustness bundle — five ready S-effort fixes (hook-cli-robustness)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.8 | status=shipped | scope=hook-cli-robustness -->

**Why:** Five independent, ready, S-effort robustness/correctness gaps in the
framework's own hook CLI + governance libs accumulated on the backlog (from
Critic/builder/reviewer notes). Each was small and isolated; the highest-ROI
structure was to bundle them on one branch so a single cumulative review + PR
amortizes the (P0) opus review wall-clock across five correctness wins rather
than paying it five times.

**What:** (1) **STH-5R2Q** — flag-only subcommands (`clear`, `audit-learnings`,
`repo-disable`) now reject unknown args via a shared `_reject_unknown_args`
helper (exit 2, the hook's usage-error convention) instead of silently ignoring
them — the swallow that had masked a real bug where a test passed `tmp_path`
positionally and the live repo was audited. (2) **TST-3E8V** —
`cmd_test_evidence` widens its launch catch `FileNotFoundError` → `OSError`, so a
non-executable `test_command` target (`PermissionError`) takes the clean exit-2
path instead of tracebacking. (3) **REL-7P3X** — `cmd_stamp_merged` strips a
leading origin/ from the configured `base_branch` before the local-branch guard
compare, so the project-state-"preferred" origin-prefixed form no longer refuses
permanently. (4) **STH-9T4F** — the critic-active marker
(`lib/critic_marker.py`) and the operator-verification queue rewrite
(`lib/operator_verification.py`) now use `core.atomic_write_text` (the two sites
left out of STH-8M3V's scope); their readers fail open, so a torn write misfired
governance silently. (5) **BLD-4K7P** — `verify-chunk-refs` no longer cries wolf
on non-path tokens: `_looks_like_file_path` skips `<>`/`://` (template
placeholders, URLs) and `_verify_chunk_refs` skips intentionally-gitignored
managed paths via a new `gitstate.git_path_is_ignored` helper. +14 tests
(1352 → 1366). Cumulative Critic caught one BLOCKING (the plan's own prose
backticked git-ref tokens that tripped the new ref check) — fixed by
de-backticking, with the general git-ref over-match captured as follow-up
BLD-3M7K. CRT-9L2F (post-release live-verify of explicit Critic mode) is the
natural follow-up once this ships.

## 2026-06-20: Resolve `.prawduct/` state against the session git worktree — governance gates + critic/pr compose in worktrees (STH-4K7N)

<!-- prawduct: chunks=01,02 | type=fix | release=v2.1.8 | status=shipped | scope=worktree-compat -->

**Why:** Host repos increasingly *mandate* git worktrees for WIP (a stable
primary checkout serving the plugin live; isolation for parallel agents), but
prawduct had no worktree story. The hooks resolved `.prawduct/` via
`CLAUDE_PROJECT_DIR` — which the harness pins to the *launch* dir (the primary
checkout) — while the agent side (skills writing relative paths, and
`prawduct-hook` invoked from a Bash `cd`'d into the worktree) resolved to the
*worktree*. So worktree-written reflection / Critic findings / cumulative records
were invisible to the Stop and cumulative-critic gates → false blocks, forcing
every worktree work cycle off-protocol (review via an independent Agent, merge
with raw `gh`). One reported bug
(`incoming-bugs/governance-gates-and-critic-pr-skills-dont-compose-with-git-worktrees.md`),
three symptoms, one root cause: hook-read and agent-written state diverged.

**What (Chunk 01 — code):** New `lib.gitstate.resolve_project_dir` makes the
project dir follow the session into its worktree — `git rev-parse --show-toplevel`
of cwd, preferred over the `CLAUDE_PROJECT_DIR` pin **only when cwd is a worktree
of the same repo** (shared `--git-common-dir` guard, so a cwd in an *unrelated*
repo still honors the pin), failing open to today's env/cwd behavior on any git
error. The hook's `get_project_dir` delegates to it and stays bootstrap-resilient
(a broken/absent plugin `lib/` falls back to the env behavior so per-command
import-error handling still fires). No-regression by construction: in a single
checkout the toplevel equals the pin, so resolution is unchanged. The two
SessionStart cosmetic scripts (`hooks/digest.py`, `hooks/banner.py`) are
deliberately *not* changed — they touch no gate state and `banner.py` refuses a
cwd fallback by design. 10 new tests (`tests/test_project_dir_resolution.py`),
including a "don't-saw-your-own-branch" self-check for this session-governing
runtime. All git operations were already worktree-safe (shared refs, per-worktree
working tree), so only state-file resolution needed the fix.

**What (Chunk 02 — docs):** `methodology/building.md` gains a "Working in a git
worktree" callout (work cycles compose in a worktree; run `/critic` and `/pr` from
there; the mid-session-enter marker edge); canonical operational notes added to
`skills/critic/SKILL.md` and `skills/pr/SKILL.md` (where they're consumed and have
token headroom) so repos stop reinventing the private workaround. building.md's
token ceiling bumped 4850 → 4950 with rationale, partly offset by a verbatim-dup
trim. A post-merge live-harness check is queued in
`.prawduct/operator-verification.md` (VRF-001) to confirm the one assumption a
unit test can't reach: that a real hook *process* runs with the worktree as its
cwd.

## 2026-06-21: Reconcile the backlog `closed-by:` handle contract — a pre-commit handle (chunk/scope/tag), never a bare SHA (backlog-closed-by-handle)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.7 | status=shipped | scope=backlog-closed-by-handle -->

**Why:** v2.1.6 (`backlog-ship-in-pr`) told builders to archive an item *on the
branch that closes it* (`closed-by=<scope>`), but only updated the "When to mark
shipped" prose — the **contract text** defining `closed-by` (the item-shape line,
the `update … closed-by` step, the template legend) still read `<chunk-id|tag>`
and never said what handle to use for **non-chunk work** (a standalone
refactor/chore committed directly). With no chunk id, a builder reaches for the
commit SHA — which a commit can't contain and which `--amend` rewrites (dangle),
forcing an extra "fix closed-by" commit: exactly the separate-bookkeeping churn
`backlog-ship-in-pr` set out to remove. Filed as an upstream report (Hallucinote,
originally `puzzles`); triaged to **BKL-9K4T**.

**What:** All four contract sites in `skills/backlog/SKILL.md` and
`templates/backlog.md` now state one rule — `closed-by` is a handle that exists
*before* the commit recording it (a chunk id, the branch/feature **scope** name,
or a release/change-log tag), **never a bare commit SHA** (can't sit in its own
commit; dangles on `--amend`) **nor an unassigned PR number**. For non-chunk work
the prescribed handle is the **branch/scope name** (resolvable on-branch, survives
amends), and the `update` step warns on a bare SHA and substitutes the scope name.
Doc-only — nothing in `lib/`/`bin/` parses `closed-by`; it is human-readable
provenance. Coherent-Artifacts (P13) fix: the v2.1.6 rule change cascaded to the
field's own contract definition.

## 2026-06-20: Formalize the upstream bug-reporting channel — /prawduct:report-bug + inbox resolver + receiving advisory (upstream-bug-reporting)

<!-- prawduct: chunks=01,02 | type=feature | release=v2.1.6 | status=shipped | scope=upstream-bug-reporting -->

**Why:** Products that consume prawduct hit bugs in prawduct *itself* and filed
reports into the prawduct checkout's gitignored `incoming-bugs/` drop-box by
hand — an undocumented method with no path-discovery, no inert behavior for
plugin-only users (who have no local writable checkout), and no formalized
triage (reports sat unarchived). The user asked to formalize it so it works when
a prawduct checkout is reachable and is harmless/inert otherwise.

**What:** A new `/prawduct:report-bug` skill files a templated report into the
inbox when one is reachable, else captures the bug in the product's *own* backlog
(`area=prawduct-upstream`) and prints the GitHub issues URL — never errors.
`prawduct-hook bug-inbox` resolves the inbox from `PRAWDUCT_BUG_INBOX` → a
gitignored `.prawduct/.bug-inbox` pointer → none (validates exists+writable;
fail-soft to none). The path is deliberately a local/machine signal, never
committed state (a non-portable absolute path must not travel to clones/CI), so
**inertness falls out of absence** — a plugin-only user configures neither
signal. Receiving side: a `untriaged-upstream-reports` session-start advisory
(`lib/upstream_probes.py`, registered in `cmd_clear`) fires only where
`incoming-bugs/` exists and is non-empty — naturally absent → inert in every
product repo — nudging triage; the triage→backlog→archive flow is documented in
the skill and the CLAUDE.md "Reviewing product feedback" route. `.bug-inbox` is a
managed `GITIGNORE_ENTRIES` entry (gitignored in every onboarded product) with
its hook-side mirror kept in parity. A terse discoverability pointer was added to
both session digests (full reaches products; slim reaches the framework repo).
New tests cover the resolver matrix, the `bug-inbox` subcommand exit-code
contract, the probe fire/inert split, and the digest pointer; both inert paths
exercised live.

## 2026-06-20: Archive a closed backlog item in the closing PR, not as a separate after-merge edit (backlog-ship-in-pr)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.6 | status=shipped | scope=backlog-ship-in-pr -->

**Why:** Guidance framed marking a backlog item `status=shipped` as a post-merge
*reconciliation* step, so closing an item required a separate bookkeeping
commit/PR after the feature merged — redundant review/PR churn. The D4 rule it
rests on ("never *infer* status from a view — the builder makes the explicit
call") constrains *how* the call is made, not *when*; nothing actually required
waiting until after merge.

**What:** The primary path is now "archive the item *on the branch that closes
it*" (`status=shipped closed-by=<scope>`), so the archive rides in the feature's
own PR and is **atomic with the merge** — an abandoned PR abandons the archive
too, so the backlog can't drift. `skills/backlog/SKILL.md` gains a "When to mark
shipped" rule and demotes "Reconcile shipped work" to the explicit fallback;
`skills/critic/review-cycle.md`'s backlog-resolution NOTE now nudges archiving
on-branch. Disambiguated: backlog `shipped` = work merged to the integration
base (its single terminal state) vs. a change-log entry's `status=shipped` =
released to consumers (`main`), which legitimately batches at the `develop→main`
release and is untouched. `methodology/building.md` is left as-is — its
chunk-close step already closes affected items on-branch before `/clear`.

## 2026-06-12: Harden reviewer-model dispatch against model withdrawal — ordered tier chains with graceful fallback (reviewer-model-fallback)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.5 | status=shipped | scope=reviewer-model-fallback -->

**Why:** Reviewer dispatch pinned concrete model aliases in skill prose (`escalate`
→ `model: fable`, `standard` → `model: opus`). Fable was temporarily withdrawn
(2026-06-12); a pinned `model: fable` with no fallback breaks every escalate-tier
review when the harness no longer lists fable as a valid model — and a withdrawn
subagent `model:` override does not fail loudly, it silently resolves to the
*session* model (the wrong tier). The user asked to harden against model changes
and chose the lightest mechanism (prose-only ordered fallbacks).

**What:** All three dispatch surfaces now express ordered tier chains plus a
withdrawn-model resolution rule — dispatch on the first chain model the harness
lists as valid; if the preferred one is withdrawn/unrecognized or errors on
dispatch, fall back to the next; record what actually ran. Chains: `escalate` →
`fable` → `opus`; `standard` → `opus` → `sonnet` (evidence:
`reviewer-model-ab-2026-06-10.md`). Canonical statement in
`skills/critic/review-protocol.md` (terse, token-budget-capped); summary in
`skills/critic/SKILL.md` step 6; self-contained copy (with the silent-substitution
rationale) in `skills/pr/SKILL.md` step 3. The Critic-fork frontmatter
(`model: opus`) is left as-is — already the fallback tier, not fable, and a single
frontmatter value can't express a chain. Contract test
`test_escalation_tier_declared` evolved to assert the two-part contract (depth tier
named **and** withdrawn-model fallback documented) — strengthened, not weakened.
`review-protocol.md` was at its `<3120`-token ceiling, so the new rule was offset
by removing genuine redundancy (a top-of-file Role comment duplicating
`SKILL.md`'s; a self-restating clause in the Simplification goal's backwards-compat
bullet) — trim, not bump; no review check dropped. Heavier-mechanism option
(single-source registry + drift check) considered and deferred as REL-5K8M. Harness
behavior verified via claude-code-guide (2026-06-12, code.claude.com/docs): per-call
and frontmatter `model:` take a single value (no fallback syntax), so resolution is
prose-driven by the runtime dispatching agent.

## 2026-06-10: Consolidate critic_mode's mirrored helpers onto buildplan_refs/gitstate + shared build-plan walkers (STH-2K8R + BLD-6Q1N)

<!-- prawduct: chunks=01 | type=refactor | release=v2.1.4 | status=shipped | scope=critic-mode-consolidation -->

**Why:** `lib/critic_mode.py` carried five re-implementations whose stated
rationale — "no dependency on `bin/prawduct-hook`; re-implemented to stay
importable from the slash-command shim" — died when STH-9V4K (v2.0.14) moved
the canonical helpers into lib siblings `critic_mode` already imports from.
The copies were live drift hazards: the 2026-06-09 review-fixes Critic
flagged the inline porcelain parse as a third parser that silently lacked
`parse_porcelain_line`'s quoted-path/rename hardening rationale trail, and
the Status-walk skeleton existed in five places (BLD-6Q1N's third-caller
threshold met twice over).

**What:** One consolidation pass, not behavior-preserving by construction
(it collapses parity relationships). (1) `critic_mode` deleted
`_is_metadata_path`/`_METADATA_PREFIXES`, `_git_head_sha`,
`_current_chunk_id_from_status`, `_chunk_ids_in_status_order`, and
`_count_build_plan_chunks`; it now consumes `lib.gitstate` and
`lib.buildplan_refs`. (2) `_get_uncommitted_code_files` keeps its own
`-uall` git call but parses lines via `gitstate.parse_porcelain_line`.
(3) BLD-6Q1N: `buildplan_refs` gains the canonical Status-section walkers
(`_iter_status_section_lines`/`_iter_status_section_items`) and chunk-section
walker (`_chunk_section_lines`); `_count_build_plan_chunks` and
`_chunk_ids_in_status_order` live there now; `gates.py` deleted its duplicate
counter and delegates. All five Status readers and all four chunk-section
parsers fold onto the shared walkers. (4) Shared-helper read errors now
catch `(OSError, UnicodeDecodeError)` — unifying gates' broad-except posture
and critic_mode's OSError-only posture (a malformed-encoding plan previously
crashed critic_mode's copy, returned (0,0) from gates'). (5) Deliberately
NOT consolidated: `_chain_extendable_anchor` ↔ `gates._chain_anchor` + the
verbose mode constants — a test-pinned mirror (`TestChainAnchorParity`)
whose rationale (keep `gates` out of the shim's import graph) still holds;
`lib/views.py`'s index-based Status rewriter (needs positions, not a
reader's view); the hook's import-light pinned mirrors. (6) New
`tests/test_buildplan_walkers.py`: walker unit coverage, porcelain edge
cases through the consolidated parse path, and consolidation pins — the
inverse of `TestChainAnchorParity`: that mirror must stay equal, these must
stay singular (source-scan + namespace assertions). Two existing
metadata-allowlist pins repointed from `lib.critic_mode` to the canonical
`lib.gitstate` home, assertions unchanged. Net −150 lines of production
code; closes STH-2K8R, BLD-6Q1N, and CRT-3D9K (by construction — merged
into STH-2K8R).

## 2026-06-10: /prawduct:critic explicit mode argument — forward to the helper, never self-parse (CRT-2N7V)

<!-- prawduct: chunks=03 | type=fix | release=v2.1.3 | status=shipped | scope=gate-hardening -->

**Why:** Invoking the Critic skill via the Skill tool with an explicit mode
(observed 2026-06-10: args `chunk`) ran inference instead — `mode_chosen_by`
recorded the rule-1b rationale, not `"explicit-args"`. Root cause confirmed
by research, not recall: Claude Code does not substitute `$ARGUMENTS` in
`context: fork` skills invoked via the Skill tool
(anthropics/claude-code#34164, closed not-planned) — the forked Critic saw
the literal placeholder, which contains no mode token, and correctly fell
through. CRT-3M8Q's fix (#58) added the plan-field override as a workaround
but left the skill prose promising an explicit-args path that can't fire on
that delivery route. Same-session evidence showed Skill-tool args DO reach
fork skills (backlog `pick`, learnings topics honored), so the arguments
arrive — the prose just told the model to read them from the one place
they're not.

**What:** Mode resolution is now delivery-agnostic and helper-owned. (1)
SKILL.md step 1: collect arguments from whichever path carried them
(substituted placeholder — now a labeled `**Invocation arguments:**` line —
launch message, or trailing `ARGUMENTS:` line; the literal unsubstituted
placeholder means "check the other paths"), then forward verbatim to
`prawduct-hook infer-critic-mode <args…>` — never self-parse. The helper
already implemented the full precedence (explicit token → `explicit-args` >
plan-override > inference; tested) and was already wildcard-allowed; the
prose was the only broken layer. (2) `review-cycle.md` layer-1 documents the
forward-never-parse rule and the harness caveat. (3)
`TestExplicitModeArgContract` pins the contract: exactly one placeholder
occurrence (more garble under substitution, zero switches to the unverified
auto-append path), the forwarding instruction, the #34164 reference, and the
wildcarded allow entry. **Live-verification status (honest):** this bundle's
own cumulative review was invoked with explicit args `cumulative` and STILL
recorded the rule-2 inference rationale — the third observation of the bug
class. Undetermined whether that invocation ran the edited skill (the
framework repo's skill source resolution is ambiguous: marketplace clone of
the released v2.1.2 vs. working tree) — so the prose fix is verified at the
helper layer (unit tests) and by contract pins, NOT yet live end-to-end.
Post-release verification filed as CRT-9L2F; if Skill-tool launch-message
delivery turns out not to reach the Critic fork at all, the escalation path
is a file-based mode request. The acceptance criterion's contract arm is
satisfied either way: the prose no longer promises an unreachable path — it
degrades to inference and the `mode_chosen_by` audit trail distinguishes the
cases.

## 2026-06-10: atomic .prawduct state writes + cmd_clear OSError resilience (STH-8M3V)

<!-- prawduct: chunks=02 | type=fix | release=v2.1.3 | status=shipped | scope=gate-hardening -->

**Why:** Only `.test-evidence.json` got the tmp+`os.replace` treatment; the
other session state files (`.session-start`, `.session-git-baseline`,
`.session-handoff.md`, `.advisories.json`) were plain `write_text`, so two
concurrent sessions on one repo could tear them — readers fail open, making
the blast radius a silently misfired gate rather than a crash. Same audit:
three unguarded I/O sites in `cmd_clear` (session-file unlink loop,
`.session-start` write, baseline write) could traceback the SessionStart hook
on an OSError, unlike the meticulously best-effort code around them.

**What:** (1) One shared `core.atomic_write_text` (tmp sibling +
`os.replace`; OSErrors propagate — callers own failure policy); converted the
four audited write sites. `.gates-waived` was in the groomed set but has no
code write site (agent-written) — nothing to convert. (2) `cmd_clear`'s
unlink loop and both marker writes are now best-effort: OSError → stderr NOTE
naming the consequence (stale carry-over / fail-closed freshness / spurious
session changes), exit 0 — verified end-to-end by a read-only-`.prawduct`
subprocess test. (3) Audited-but-already-done: `_get_session_changed_files`
already had its `(UnicodeDecodeError, OSError)` guard. Out of scope, noted
for backlog: two further non-atomic sites (`lib/critic_marker.py`,
`lib/operator_verification.py`).

## 2026-06-10: shared session Critic gate — extract diverged freshness check to lib/gates.py (STH-4F7C)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.3 | status=shipped | scope=gate-hardening -->

**Why:** The mtime-vs-session-start Critic-findings freshness check was
duplicated nearly verbatim between `cmd_stop`'s blocking gate
(`bin/prawduct-hook`) and the session-start advisory
(`lib/briefing.py::_check_previous_session_gates`) — and the copies had
already diverged: cmd_stop gained the v1.5 verify-resolutions scope check,
the advisory did not, so the session-start advisory reported a fresh
verify-resolutions record as satisfying even when the session diff had
outgrown its declared scope. Unlike the hook's parity-pinned inline mirrors,
this pair had no parity test and no import-light rationale (the advisory copy
already lives in `lib/`).

**What:** (1) One shared `gates.critic_findings_satisfy_session_gate`
(freshness with the STH-6B4R strict-`>` whole-second compare, schema
validation, verify-resolutions scope subset) — both consumers delegate; the
returned scope reason preserves cmd_stop's two distinct blocker variants.
(2) The advisory now warns "Critic review stale — verify-resolutions scope
exceeded: …" on the case it previously passed (the live gap). (3) Tightened
fail-closed: an empty `.session-start` marker now rejects (the old inline
copies compared against `""` and failed open), matching CRT-8W3F's stance.
(4) `tests/test_session_critic_gate.py`: truth-table unit tests, the advisory
regression test, and a source-level guard that neither former host re-grows
an inline freshness computation.

## 2026-06-10: learnings.md compaction + size nudge (MET-6W3J)

<!-- prawduct: chunks=03 | type=fix | release=v2.1.2 | status=shipped | scope=do-next -->

**Why:** learnings.md had grown to ~80KB / 58 entries with 300–600-word
narrative bodies, drifting from its own stated format (rule here, full context
in learnings-detail.md). Every `/prawduct:learnings` lookup and Critic
learnings cross-check pays the whole file, and nothing nudged it back down —
the prior 8KB clear-hook warning was retired when the fork-skill lookup
landed, but at 80KB the lookup itself became the cost.

**What:** (1) 48 of 58 entries compacted to their When-X-do-Y-because-Z rule;
all 48 narrative bodies moved VERBATIM to learnings-detail.md (79.5KB →
32.3KB; headings byte-identical, audit-learnings parse unchanged). Navigation
is by CONVENTION, stated once in the preamble: narrative lives in
learnings-detail.md under the SAME heading (the one historical heading
mismatch was aligned). Per-entry `Detail: § <heading>` pointers were built
first, but repeating 57 long headings cost ~8KB and pushed the file back over
its own threshold — the convention replaces them. (2) Session briefing nudges
when learnings.md exceeds 40KB (the project-state threshold/pattern),
teaching the compaction fix. (3) Found while landing the nudge: the
briefing's "Learnings (N rules)" line counted only `- ` bullets, reporting 0
and silently vanishing on entry-format files — now counts `## ` entries with
bullet-count fallback for legacy files.

## 2026-06-10: build-plan pointer — repo-relative acceptance + loud missing-file guard (STH-5P2W)

<!-- prawduct: chunks=02 | type=fix | release=v2.1.2 | status=shipped | scope=do-next -->

**Why:** A SET `active_build_plan` pointer that resolves to no file silently
disables the Critic gate, plan-aware mode inference, and chunk-ref
verification — governance sees "no active plan" with zero signal. Happened
live: the review-fixes planning commit wrote the natural repo-relative
spelling (`.prawduct/artifacts/…`) and the gates were blind for one work
cycle. The field was also undocumented in the project-state template
(escape-hatches-create-silent-failures shape).

**What:** (1) Both resolvers (`lib/core.py::resolve_build_plan_path` and the
parity-pinned `bin/prawduct-hook::_resolve_build_plan_path` mirror) accept the
repo-relative spelling by stripping one leading `.prawduct/` — parity tests
extended. (2) The session briefing (`lib/briefing.py`) warns loudly when the
pointer is set but the resolved file is missing, naming the pointer, the
resolved path, and the consequence. (3) `templates/project-state.yaml` gains
an ACTIVE BUILD PLAN section documenting the field's schema and failure mode.

## 2026-06-10: PR-gate ledger fallback requires same-session freshness (CRT-8W3F)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.2 | status=shipped | scope=do-next -->

**Why:** `check_cumulative_critic`'s ledger fallback accepted the newest
kind-qualifying `review.critic` event with only commit-coverage — no freshness
bound. The findings file is a single overwritten slot, but the ledger keeps
every review forever, so a days-old cumulative from prior work could satisfy
the PR gate whenever only `.md` changed since (gate-soundness hole, flagged by
the 2026-06-10 governance audit of the v2.1.0 chain-gate code).

**What:** `_ledger_fallback_record` (lib/gates.py) now accepts a qualifying
event only when its envelope `ts >= .prawduct/.session-start` (the
`tests_are_current` ISO-string model, via a shared `_read_session_start`
helper). Fail closed: missing/unreadable marker or a ts-less qualifying event
yields no fallback — the gate's honest wrong-mode / chain-missing-anchor
message stands, and each skip is taught on stderr. Contract renegotiation in
the open: fallback-accept tests now declare a `.session-start` marker; new
`TestGateLedgerFallbackFreshness` pins the reject family. Prose surfaces
(`skills/pr/review-protocol.md` step 4, `skills/critic/review-cycle.md` ledger
section) state the bound.

## 2026-06-10: change-log lifecycle hardening — close the silent-drop family

<!-- prawduct: chunks=01,02,03 | type=fix | release=v2.1.1 | status=shipped | scope=changelog-lifecycle -->

**Why:** The change-log state machine (statusless → merged → shipped) was
broken at three transitions, all silent, all observed live (REL-9F2T): the
merge flow never stamped `status=merged`, so most entries reached release-prep
statusless and a literal reading of release-process step 3 dropped them
(v2.0.14: 8 of 10); a code-changing branch could merge with NO entry at all
(found at the v2.0.16 release reconstruction); and `parse_change_log` honored
only the FIRST tag line per entry, silently dropping later ones (a `chunks=02`
tag nearly shipped unflipped at v2.1.0). A fourth, from the 2026-06-10 audit:
scope→plan validation skipped statusless entries entirely.

**What:** (01) `parse_change_log` consumes all consecutive tag lines —
`chunks=` unioned order-preserving, scalar keys first-wins with conflicts
recorded — and `validate_tag_line_multiplicity` surfaces multi-tag entries as
regen-views stderr WARNINGs. (02) New `prawduct-hook stamp-merged` (convergent,
idempotent, integration-branch-guarded) applies the statusless→merged stamp;
`/prawduct:pr` merge flow runs it as step 6; release-process step 3 now flips
"every unreleased entry, statusless OR merged"; `diagnose_scope_plan_coverage`
also flags statusless tagged scopes with no plan file. (03) New `prawduct-hook
check-change-log-entry` probe at `/prawduct:pr` Create Step 1c: a non-`.md`
branch diff must ADD a change-log entry header, fail-closed on un-evaluable
git state.

## 2026-06-10: framework-repo slim session digest — always-loaded context dedup

<!-- prawduct: chunks=4 | type=feature | release=v2.1.0 | status=shipped | scope=review-fixes -->

**Why:** In the prawduct framework repo the always-injected session digest
(~5.4k chars, re-injected on every compaction) duplicated 40–50% of the
always-loaded CLAUDE.md nearly 1:1 (principles roster, Critic/Stop
explanation, attribution rule, rigor scaling). The digest is the legitimate
and ONLY carrier of those rules for product repos (thin-anchor CLAUDE.md), so
the fix must not gut it — per the plan-level assumption (user-confirmed
2026-06-10), the variant is selected per-repo, full stays the product default.

**What:** New canonical `methodology/session-digest-slim.md` (~2.2k chars,
budget-pinned ≤50% of full): pointers to CLAUDE.md plus only the rules
CLAUDE.md does not restate (waiver pragma, backlog discipline, branch/PR
rule, condensed agent stance, on-demand skill index). `hooks/digest.py`
gains `is_framework_repo` — the governed repo (`CLAUDE_PROJECT_DIR`) is the
framework iff `.claude-plugin/plugin.json` at its root parses to
`name: prawduct`; ANY anomaly (missing, unreadable, malformed, non-dict,
other name) fails safe to the full digest, and a framework repo served by an
older cached plugin without the slim file falls back to full (never
silence). **Declared deviation from the chunk's surface list:** the
two-variant documentation lives in `hooks/digest.py`'s module docstring and
the slim file's own header — NOT inside `methodology/session-digest.md`,
whose entire body is injected verbatim into every product session
(meta-documentation there would pollute the payload).
`tests/test_briefing_functions.py` and `tests/test_v5_methodology.py`
needed no changes (verified: neither asserts digest presence/content).

**Blast radius:** `hooks/digest.py`, `methodology/session-digest-slim.md`
(new), `tests/test_plugin_methodology_digest.py` (+11: variant selection
incl. all fail-safe paths, slim canonical-copy + budget pins, both-variant
load-bearing pointers; `test_additional_context_matches_source`
renegotiated in the open — ROOT is the framework repo, so the emitted
context is now the slim source; full-verbatim contract moved to the product
fixture). Live acceptance: `hooks/digest.py` in this repo emits the slim
variant (2,189 chars); a product fixture gets the full digest verbatim.

## 2026-06-10: PR-reviewer scoping — consume the Critic record, audit it, review the release

<!-- prawduct: chunks=05 | type=feature | release=v2.1.0 | status=shipped | scope=review-proportionality -->

**Why:** The PR reviewer re-derived code soundness over the same
`merge-base...HEAD` the cumulative-Critic gate had just certified — the
third structural tax this plan removes. Independence is preserved by
*auditing* the record, not repeating its work.

**What:** `skills/pr/review-protocol.md` rewritten around the
consume-and-audit design: the gate-qualifying Critic record is an input
(resolved the same way `check-cumulative-critic` resolves it — latest
findings file when its kind qualifies, else the newest qualifying
`review.critic` ledger event), consumed as **evidence, not truth**. Audit
duty: adversarially spot-check ≥2 substantive claims against the code; ANY
failure (or no qualifying record) voids the record → full code-soundness
pass, declared in the output. Evidence gains `mode`
(`pr-scoped`/`pr-full`), `model`, `duration_seconds`, `record_consumed`,
`spot_checks` — telemetry separates scoped from full runs with zero
telemetry-code change (mode flows through the existing grouping). Release
focus sharpened: migration/rollback notes + version/changelog coherence
bullets added to Merge Hygiene. `skills/pr/SKILL.md`: Step 3 hands the
record source to the reviewer; Step 4 (and Update flow re-reviews) append
`review.pr` to the governance ledger so role-vs-role model-efficiency
(data requirement 1) has both review roles. `lib/ledger.py`: `review.pr`
event kind (role `pr`) — requires the caller-computed `--findings <path>`,
rejected for `review.critic` (canonical-source property preserved);
payload validated at the stop-hook PR-gate bar (findings list + non-empty
summary). The cumulative-Critic gate ignores `review.pr` events (pinned —
a PR review must never vouch for code soundness).

In-cycle fixes (no pre-existing exception): ch.04 wired
`classify-diff-risk` into pr/SKILL step-3 prose but missed the
`allowed-tools` frontmatter — added (with a structural pin, parallel to
the Critic's). Deduplication (user-directed critical eye): the layering
rationale was stated 3× in review-protocol.md (intro ¶ + goals preamble +
table) → now intro + table; the retired-trivial-fast-path history was
restated in full 3× across the two files → full rationale lives in SKILL
Step 1b, the other two point at it; the `## Important` bullets restating
Steps 1b/2/2b verbatim → one-line pointers.

**Blast radius:** Modified: `skills/pr/review-protocol.md` (rewrite),
`skills/pr/SKILL.md` (allowed-tools, Steps 3/4, Update flow, Important
trim), `lib/ledger.py` (review.pr), `skills/critic/review-cycle.md` +
`docs/governance-telemetry.md` (event-kind docs current). Tests:
`tests/test_governance_ledger.py` (+9: TestLedgerAppendReviewPr + gate
honesty), `tests/test_pr_reviewer.py` (+7: TestPrReviewerScoping),
`tests/test_review_stats.py` (+1: pr-scoped/pr-full distinct modes),
`tests/preferences/test_risk_escalation_prose.py` (+1: pr allowed-tools).
1181 total.

## 2026-06-10: risk-surface reviewer escalation — `classify-diff-risk`

<!-- prawduct: chunks=04 | type=feature | release=v2.1.0 | status=shipped | scope=review-proportionality -->

**Why:** Proportionality only ran one way — review depth scaled by size/type,
never by diff RISK — yet the reviewer A/B/C experiment
(`reviewer-model-ab-2026-06-10.md`) showed the top-tier reviewer catching 2
real warnings opus missed precisely on a governance-gate bundle. That bundle
class should buy depth; everything else stays on the efficiency-frontier
default.

**What:** New classifier `prawduct-hook classify-diff-risk [<base>]` (new
`lib/risk.py`). Resolution order: explicit `risk_surfaces:` list in
`project-state.yaml` (product-ownable; EXCLUSIVE when present — an empty
list is a deliberate opt-out) → else derived defaults (`skills/`,
`lib/gates*`, `bin/*hook*`) plus literal backticked contract paths from
`boundary-patterns.md` (globs/slash-commands excluded via the shared
`_looks_like_file_path` rule). Scope = committed `merge-base(base)...HEAD`
paths + working-tree changed/untracked paths
(`--untracked-files=all` — the porcelain default collapses untracked dirs
to one line, silently hiding files from glob surfaces; caught by the new
tests). Verdict is a single stdout token `escalate`/`standard`; matched
files teach on stderr. Failure asymmetry: fail-OPEN to `standard` only when
no surfaces are declared; fail-CLOSED to `escalate` when surfaces are
declared but git evaluation fails — declared risk with an unverifiable diff
never gets the cheap reviewer. Dispatch wiring: Critic coordinator
(`review-protocol.md` — `final`/`cumulative` dispatch `model: fable` on
`escalate`, else `opus`; `chunk`/`verify-resolutions` always default-tier),
Critic SKILL step 6 + allowed-tools, PR reviewer dispatch (`pr/SKILL.md`
step 3). The findings `model` field records what actually ran, so ch.03's
telemetry will show whether escalation pays. Protocol token budget held
<3120 by displacement (mode-resolution + ledger-append paragraphs now point
at SKILL.md instead of restating it). Live check: this branch classifies
`escalate` (5 matched paths). New prose pins:
`tests/preferences/test_risk_escalation_prose.py`.

In-cycle fix (no pre-existing exception): the audit-learnings CLI smoke test
passed `tmp_path` as a positional arg the CLI ignores, silently auditing the
REAL repo (~13s) — this chunk's added parallel load pushed it past the 30s
pytest-timeout, killing the xdist worker. Now targets its tmp repo via
`CLAUDE_PROJECT_DIR` (same assertions, <1s, deterministic); the
ignored-unknown-args wart filed to backlog.

**Blast radius:** New: `lib/risk.py`, `tests/test_classify_diff_risk.py`
(21 tests — incl. lib.risk helper units added post-review to resolve the
chunk Critic's evidence-attribution NOTE),
`tests/preferences/test_risk_escalation_prose.py` (6 tests).
Modified: `bin/prawduct-hook` (wrapper + dispatch + usage),
`skills/critic/SKILL.md`, `skills/critic/review-protocol.md`,
`skills/pr/SKILL.md`, `tests/test_audit_learnings.py` (env-target fix).
1164 total.

## 2026-06-10: review telemetry — `prawduct-hook review-stats`

<!-- prawduct: chunks=03 | type=feature | release=v2.1.0 | status=shipped | scope=review-proportionality -->

**Why:** The ledger (ch.02) records review history but nothing aggregates it —
"is review worth it" stays a vibe. Visible Costs (Principle 9) applied to the
framework: proportionality arguments need cost and actionable-finding-yield
numbers, per reviewer role × model × mode (data requirement 1), per code path
(requirement 2), per feature scope (requirement 3's join seam).

**What:** New subcommand `prawduct-hook review-stats [--json]` (new
`lib/telemetry.py`; thin hook wrapper per the established lazy-import
pattern). Reads `.prawduct/.governance-ledger.jsonl` oldest-first; reports on
`review.*` events only, skipping corrupt lines / unknown event kinds (a
future `build.chunk` producer) / unusable payloads each WITH A COUNT, never
silently. Missing ledger → "no review history", exit 0 (an answer, not an
error); exit 1 only on bad args. Per grouping (overall, role×model×mode,
per-scope): review count, total/median duration, findings by severity
(blocking/warning/note + `other` so unexpected severities stay visible),
actionable rate (share of reviews with ≥1 blocking/warning),
findings-per-review. Findings-by-file rollup from per-finding `files`
attribution — top 10 by actionable findings, with `files_attributed_total`
alongside so the cap is visible. `--json` emits the stable machine shape
(top-level `schema_version`/`project`/`generated_at`) that TEL-7A4X builds
on; keys pinned by tests so a change must consciously bump
REPORT_SCHEMA_VERSION. The reader deliberately does NOT reuse
`ledger.iter_events_newest_first` (different contract: quiet counts vs the
gate's newest-first stderr notes). Surfacing: one orient-step pointer in
`/prawduct:janitor` — telemetry is pulled, not pushed. Documented in new
`docs/governance-telemetry.md` (event schema + report contract). Dogfood:
runs clean on this repo's real 2-event ledger — the first genuine
cost/actionable-rate numbers.

**Blast radius:** New: `lib/telemetry.py`, `tests/test_review_stats.py`
(12 tests), `docs/governance-telemetry.md`. Modified: `bin/prawduct-hook`
(wrapper + dispatch + usage), `skills/janitor/SKILL.md` (one line). 1137
total.

## 2026-06-10: governance-event ledger — append-only review history + PR-gate fallback

<!-- prawduct: chunks=02 | type=feature | release=v2.1.0 | status=shipped | scope=review-proportionality -->

**Why:** The single-slot `.critic-findings.json` forces a choice between
reviewing new work and preserving the PR-gate record (observed twice on
2026-06-10: a review deferred-and-declared, a chunk review that would have
clobbered the gate's evidence) — and review history is unmeasurable because
each record overwrites the last (Principle 9, Visible Costs, unapplied to
the framework itself).

**What:** Append-only governance-event ledger at
`.prawduct/.governance-ledger.jsonl`, ADDITIVE — the findings file stays the
canonical latest record all existing consumers read. Schema shaped by the
user-elicited "Ledger data requirements" (not mechanism-first): per-line
`schema_version`, envelope/payload split (`{schema_version, event, ts,
duration_seconds, project, scope, chunk, actor:{role,model}, git:{head,base}}`
+ kind-named payload), consumers skip unknown kinds/fields. v1 emits
`review.critic` only; unknown kinds REJECTED at append (fail closed).
Structural writer `prawduct-hook ledger-append` (new `lib/ledger.py`):
agents never hand-author JSONL — the helper validates the findings file
(same schema the gates trust), computes the envelope itself, appends one
O_APPEND line; `--scope` explicit from the reviewer (side-plan
mis-attribution), `active_build_plan` only the fallback (frontmatter
`scope:` → filename); duration/model nullable, never invented. PR-gate
ledger fallback (`check_cumulative_critic` refactored into
`_pr_gate_record_qualifies` / `_ledger_fallback_record` /
`_evaluate_pr_gate_record`): when the latest record is the wrong KIND
(chunk/final, or verify with no chain anchor), scan the ledger newest-first
for the first qualifying `review.critic` payload and evaluate it under the
unchanged checks — stale/blocking ledger records still fail honestly,
corrupt lines skip with a stderr note, no qualifying event → today's exact
failure messages. Findings schema gains optional `model` (record level) and
per-finding `files` (risky-areas attribution). Producers: Critic SKILL step
7 + review-protocol Output Format instruct the append (allowed-tools gains
`Bash(prawduct-hook ledger-append *)`); protocol budget held <3120 by
displacement. Hygiene: gitignore entry in all three mirrors (core
GITIGNORE_ENTRIES, hook _SESSION_GITIGNORED_PATHS — caught live by
TestSessionGitignoreMirror — and this repo's .gitignore); event shape
documented in review-cycle.md "Recording Reviews" + project-structure.md;
prune escape hatch is prose only (truncate oldest lines; no tooling until a
real ledger needs it). Critic `final` (explicit override, side-plan
convention): 0 blocking, 0 warnings, 2 NOTEs (defensive-branch comment
added; tag confirmed). The Critic dogfooded `ledger-append` recording its
own review — first real event, correctly scope-attributed.

**Blast radius:** New: `lib/ledger.py`, `tests/test_governance_ledger.py`
(36 tests). Modified: `lib/gates.py`, `lib/core.py`, `bin/prawduct-hook`,
`.gitignore`, `skills/critic/SKILL.md`, `skills/critic/review-protocol.md`,
`skills/critic/review-cycle.md`, `docs/project-structure.md`. 1125 total.

## 2026-06-10: cumulative-as-final — one full review per plan, not two

<!-- prawduct: chunks=01 | type=feature | release=v2.1.0 | status=shipped | scope=review-proportionality -->

**Why:** `Type: cumulative-final` was *defined* as the last chunk's `final`
review PLUS a cumulative — two 4-10 min full reviews over nearly the same
diff, on every multi-chunk plan. Cumulative is a strict superset of final
(all 7 goals + cross-checks over `merge-base...HEAD` ⊇ the chunk diff), so
the second pass re-bought assurance already paid for. Gate-soundness ch.05
already did the right thing ad hoc as a declared deviation; this makes it
the rule (review wall-clock is P0).

**What:** Redefined `cumulative-final`: commit the last chunk first, then run
`/prawduct:critic cumulative` ONCE — that review IS the chunk's review and
the PR-gate record; post-cumulative fixes ride the CRT-4J8W chain. Prose on
four surfaces (`skills/critic/review-cycle.md` Type matrix + When-Review-Is-
Required rows + a new Per-Chunk-Cycle sequencing note documenting the
rule-3-final-is-mid-chunk / rule-2-cumulative-is-at-commit inference
distinction; `methodology/planning.md` Critic-Mode override bullet +
`cumulative-final` Type description; `methodology/building.md` Skipping-final
trap; `templates/build-plan.md` Type list + Done-when comment + PR-cadence
example — the template was a Critic WARNING catch, the chunk's own surface
enumeration missed it). No code change: inference already sequences correctly
(rule-3 `final` fires only on UNCOMMITTED last-chunk work; rule-2 picks
`cumulative` once committed and clean). New
`TestSynthesisAdvisoryAcceptsCumulative` pins that the stop-hook synthesis
advisory accepts a `cumulative` closer and still trips on
`chunk`/`verify-resolutions` (no prior pin existed — an untested governance
bound rots silently). Also shipped the schema-lock-in tripwire from this
plan's own near-miss: `methodology/planning.md` ("A persisted format is
always a lock-in decision" — consumers' future queries are the requirements,
reversal cost not LOC) + condensed into `methodology/building.md` Decision
Research lock-in trigger. building.md budget held by displacement (<4850):
PR-gate paragraph condensed to a review-cycle.md pointer, in-file duplicate
mode-list/inference-default lines collapsed.

**Blast radius:** `skills/critic/review-cycle.md`, `methodology/planning.md`,
`methodology/building.md`, `templates/build-plan.md`,
`tests/test_critic_gate_fallthrough.py` (+4 tests, 1089 total).

## 2026-06-10: chain gate — cumulative + verify-resolutions at the PR gate (CRT-4J8W)

<!-- prawduct: chunks=05 | type=feature | release=v2.1.0 | status=shipped | scope=gate-soundness -->

**Why:** Review cost = unit-cost × run-count. Reviewer-model tiering fixed
unit cost; run-count was still gate design: every non-`.md` fix after the one
cumulative re-staled `check-cumulative-critic` and cost a FULL bundle
re-review (~4-10 min) even for a 2-file fix. User P0 escalation 2026-06-10;
the gate-soundness ch.4 "build if it recurs" trigger fired the same session.

**What:** `check-cumulative-critic` now accepts EITHER a HEAD-covering
cumulative record (unchanged) OR a chain record: `verify-resolutions` mode,
`extends_cumulative` anchor X resolving, 0 BLOCKING, own `commit_reviewed`
covering HEAD (same doc-only allowance), and all non-`.md`/non-metadata files
in `X..HEAD` ⊆ `files_reviewed` — fail closed on any gap. Soundness:
cumulative@X vouches for the bundle; a clean delta review whose scope covers
`X..HEAD` extends that vouching to HEAD. Producer side: the scope helper
emits `extends-cumulative=<X>` for chain-extendable priors (cumulative, or
chain records — the anchor propagates) and no longer demotes a clean
cumulative prior that has a reviewable delta; the Critic embeds the anchor
(schema: optional `extends_cumulative` dict, malformed shapes rejected).
Inference: new rule 1b picks `verify-resolutions` for a committed
post-cumulative fix (else no-args `/prawduct:critic` re-pays a full bundle
review), and rule 2 skips when a chain record covers HEAD. Gate stderr
teaches the new sequence (`chain-stale` says commit BEFORE verify;
`chain-scope-gap` names uncovered files). Declared decision: the anchor
embeds for ANY prior cumulative incl. one with BLOCKINGs — the verify pass
adjudicates resolution and the gate accepts only 0-BLOCKING chain records;
restricting to clean priors would leave the blocking-fix loop on the
treadmill.

**Blast radius:** `lib/gates.py` (`validate_critic_findings`, `_chain_anchor`,
`_compute_verify_resolutions_scope`, `_record_covers_head`,
`check_cumulative_critic`), `lib/critic_mode.py` (rule 1b, rule-2 skip,
`_chain_extendable_anchor`), `skills/critic/SKILL.md` + `review-protocol.md`
+ `review-cycle.md`, `skills/pr/SKILL.md` Step 2, `methodology/building.md`
(both budget files trimmed to hold), `tests/test_cumulative_gate.py` (chain
accept/reject + scope-helper chain cases), `tests/test_critic_mode_inference.py`
(rule 1b, rule-2 skip, `extends_cumulative` schema).

## 2026-06-10: reviewer model tiering — A/B/C experiment + opus default

<!-- prawduct: chunks=01,02 | type=feature | release=v2.1.0 | status=shipped | scope=reviewer-model-tiering -->

**Why:** Independent reviewers (Critic fork, PR reviewer, coordinator
subagents) inherited the main session's model — top-tier cost and latency
(5-10 min per review) for every review. User escalated review-phase wall
clock to P0 (30+ min of review for ~5 min of work this session).

**What:** Ch.01 — captured A/B/C: three parallel agents, identical prompt
(recorded verbatim in `artifacts/reviewer-model-ab-2026-06-10.md`), identical
tree, models sonnet/opus/fable. Result: sonnet found nothing novel at higher
cost than opus (ruled out); opus = efficiency frontier (1m53s, 74k tokens,
one novel real finding); fable = deepest (2 real warnings opus missed) at
~4x opus wall clock. Ch.02 — per the user's decision, all three reviewer
legs default to `opus`: critic SKILL frontmatter `model: opus` (applies to
the fork), coordinator dispatch declares `model: opus` per Agent call, PR
skill Step 3 passes `model: opus`. Declared deviation: ch.02's own Critic
review is deferred (a re-run would overwrite the cumulative record that
satisfies the open PR gate — single-slot findings file); the diff is .md-only
and rides the gate-soundness PR's independent review. The treadmill half of
the P0 is designed and filed ready-to-build as CRT-4J8W (cumulative +
verify-resolutions chain at the PR gate).

**Blast radius:** `skills/critic/SKILL.md`, `skills/critic/review-protocol.md`
(within token budget after trim), `skills/pr/SKILL.md`,
`.prawduct/artifacts/reviewer-model-ab-2026-06-10.md` (new),
`.prawduct/artifacts/build-plan-reviewer-model-tiering.md` (new),
`.prawduct/backlog.md` (CRT-4J8W).

## 2026-06-10: pre-PR hardening from the reviewer-model A/B/C experiment (gate-soundness)

<!-- prawduct: type=fix | release=v2.1.0 | status=shipped | scope=gate-soundness -->

**Why:** The reviewer-model-tiering experiment (chunk 01 of that plan) ran
three identical independent reviews of this bundle on sonnet/opus/fable. The
fable run surfaced two real warnings the official record missed: (1) JUnit
parsing read only the FIRST `<testsuite>` — safe under pytest, but
`test_command` invites multi-suite runners (jest-junit, merged CI reports)
whose counts would be silently undercounted in gate-trusted evidence; (2) the
`init_product` `unignored` presentation layer — the exact seam that absorbed
two ch.3 Critic warnings — shipped untested. Per the project rule that
warnings are effectively blocking, fixed before PR rather than backlogged.

**What:** Counts now sum across all top-level `<testsuite>` elements (direct
children, so Ant-style nesting can't double-count) — pinned by a multi-suite
fake-runner test. Two presentation tests pin `init_product.run`'s text-mode
git-add advice and `--json` `unignored` field. Plus the experiment's smaller
catches: `argv` shadowing renamed (`run_argv`); skip-scope test renamed and
ch.1 change-log phrasing tempered (the unjudged listing is producer-attested
— the pinned contract is per-listed-file skip, not tamper-proofing); stale
`project-state.yaml` pointer narrative and `planning.md` stop-hook
trigger wording fixed; `#`-truncation caveat documented on `test_command`;
CRT-8D2W misattribution corrected and BLD-7W2J (parallel-plans single-slot
pointer) filed via /prawduct:backlog. 1050 pass.

**Blast radius:** `bin/prawduct-hook` (JUnit aggregation, rename),
`tests/test_plugin_runtime.py`, `tests/test_gitignore_management.py`,
`tests/test_verify_coverage_gate.py`, `templates/project-state.yaml`,
`methodology/planning.md`, `.prawduct/project-state.yaml`,
`.prawduct/backlog.md`, `.prawduct/change-log.md`.

## 2026-06-10: cumulative-gate ordering guidance + plan-lifecycle note (gate-soundness ch.4)

<!-- prawduct: chunks=04 | type=fix | release=v2.1.0 | status=shipped | scope=gate-soundness -->

**Why:** The natural review loop (cumulative → fix findings → verify-resolutions)
can never satisfy `check-cumulative-critic` — the gate accepts only a
cumulative-mode record at HEAD (or .md-only since). That rule was learnable
only by paying a full ~4-10 min re-review (scriob PR #43 did). And the
"don't repoint `active_build_plan` while the prior plan is release-pending"
rule lived only in the PR-merge flow, invisible at planning time where the
repointing mistake actually happens.

**What:** The gate's `wrong-mode` stderr now teaches the sequencing rule
inline (verify-resolutions can't certify the bundle; land all non-.md fixes
first, cumulative once, last) — pinned by test. `skills/pr/SKILL.md` Step 2
gains the explicit Sequencing paragraph; `methodology/building.md`'s
cumulative-gate paragraph folds the rule in word-neutrally (prep-list examples
live on in the PR skill); `methodology/planning.md` Build Planning gains the
gitflow plan-lifecycle paragraph (retain the pending plan's pointer until the
release ships; scope-named plan files; plans are tracked artifacts). No gate
semantics changed — guidance and error-message teaching only. 1047 pass.

**Blast radius:** `lib/gates.py` (message text), `skills/pr/SKILL.md`,
`methodology/building.md`, `methodology/planning.md`,
`tests/test_cumulative_gate.py`.

## 2026-06-10: build plans are tracked artifacts (gate-soundness ch.3)

<!-- prawduct: chunks=03 | type=fix | release=v2.1.0 | status=shipped | scope=gate-soundness -->

**Why:** The framework gitignored `.prawduct/artifacts/build-plan.md`
(`GITIGNORE_ENTRIES`) while tracked `project-state.yaml` pointed
`active_build_plan:` at it and `/prawduct:pr` step 7 retains the plan through
a gitflow release-pending window — so every multi-clone repo carried a tracked
pointer to a file the other clones don't have (scriob PR #43: broken
verify-chunk-refs + views error, invisible locally). Worse,
`_untrack_session_files` force-`git rm --cached`'d a tracked plan at every
session start, actively reverting the product's fix. A build plan is a
durable, multi-session, release-spanning artifact — not session state; the
ignore default also made resumed sessions blind to committed decompositions
(scriob's "plan invisible to git status" learning).

**What:** Entry removed from both `GITIGNORE_ENTRIES` and the hook's
`_SESSION_GITIGNORED_PATHS` (mirror-parity test pins them together); new
`RETIRED_GITIGNORE_ENTRIES` list that `update_gitignore` strips from existing
repos, reported via `unignored` and plumbed through `init_product` (text +
json output) so onboard advises `git add`. Declared deviation: a new thin
`prawduct-hook update-gitignore` subcommand is the doctor repair path
(init-product early-exits on onboarded repos; session hooks must never edit a
tracked file). Doctor health-check 8 covers the gitignore contract; doctor's
F4 wording aligned with ch.1. This repo's own `.gitignore` line removed.
First behavioral tests for `update_gitignore` (previously untested guard).
1047 pass.

**Blast radius:** `lib/core.py`, `lib/init_product.py`, `bin/prawduct-hook`,
`.gitignore`, `skills/doctor/SKILL.md`, `skills/onboard/SKILL.md`,
`tests/test_gitignore_management.py` (new). Critic (chunk ×2): 0 blocking;
ch.3-pass-1 warning (unignored report had no consumer) and pass-2 warning
(onboard text-mode never printed it) both fixed; note (declare the subcommand
deviation in the plan) adopted.

## 2026-06-10: test-evidence configurability — `test_command:` + `tests_dirs:` (gate-soundness ch.2)

<!-- prawduct: chunks=02 | type=feature | release=v2.1.0 | status=shipped | scope=gate-soundness -->

**Why:** `test-evidence record` hardcoded `sys.executable -m pytest` from the
repo root with a single `tests/` grep dir. On a uv-managed venv the hook's
interpreter can't import the product package; on a monorepo there's no root
pytest config and tests live in component trees; the verifier took ONE
`--tests-dir` and `--merge-into` overwrote, so multi-tree products needed a
multi-pass temp-file union. scriob's 90-line `scripts/test-evidence.sh`
wrapper is the requirements doc this chunk implements.

**What:** Two optional `project-state.yaml` knobs. `test_command:` — the
canonical suite invocation (the exact command CI runs), shlex-split (never a
shell — the subprocess-safety guardrail caught the originally-planned
`shell=True`; deviation declared in the build plan) and run from the repo
root; must contain `{junit_xml}` (substituted per-token after splitting);
extra CLI args rejected; missing executable is a clean exit-2. `tests_dirs:`
— whitespace-separated trees forwarded to the verifier, whose `--tests-dir`
is now repeatable with union discovery (one run covers all trees; no merge
dance). No knobs ⇒ behavior unchanged (regression-pinned). Also fixed ch.1
coherence drift in `methodology/building.md`/`templates/project-state.yaml`
("every change" → judged/unjudged contract), trimming within the building.md
token budget. 8 new tests; 1038 pass.

**Blast radius:** `bin/prawduct-hook` (`cmd_test_evidence`),
`bin/test-reference-verify` (`--tests-dir` append), `templates/project-state.yaml`,
`methodology/building.md`, `tests/test_plugin_runtime.py`,
`tests/test_reference_verifier.py`. Critic (chunk mode): 0 blocking, 1 warning
(plan-vs-code shell-semantics drift — plan deviation declared, docstring
fixed), 2 notes (FileNotFoundError handling, substitute-after-split — both
adopted).

## 2026-06-10: coverage gate honesty — `changes_unjudged` (gate-soundness ch.1)

<!-- prawduct: chunks=01 | type=fix | release=v2.1.0 | status=shipped | scope=gate-soundness -->

**Why:** The F4a producer (`bin/test-reference-verify`) symbol-greps Python only,
but the F4b consumer (`verify_coverage`) compared the WHOLE branch diff +
untracked files against `changes_referenced` — so docs, configs, fixtures,
symbol-less `__init__.py`, and deletions failed the gate by construction.
scriob hit this three times (learnings `confirmations=3`) and then neutralized
the gate by unioning the full branch diff into `changes_referenced` (4ca5bd3) —
an unsatisfiable gate trained the product to make it vacuous.

**What:** The verifier now classifies each changed file: judged (Python with
≥1 def/class symbol) vs unjudged (non-Python, symbol-less Python, deleted) —
new evidence field `changes_unjudged`; the filename-stem fallback is dropped
(noise both directions; contract renegotiated in the open —
`test_non_python_file_is_unjudged_not_stem_matched`). The gate skips files
listed unjudged or absent from disk, reporting them in one informational
stdout line, and still exits 1 with BLOCKING `missing-coverage:` for judged
Python files no test references — severity language untouched, no
blocking→warning demotion anywhere. Legacy/product evidence without the field
keeps the old contract (absent ⇒ empty). First direct test module for the
F4b gate (`tests/test_verify_coverage_gate.py`), including the skip-scope
case (only LISTED files are skipped; an unlisted judged gap still blocks —
the listing itself is producer-attested, same trust model as
`changes_referenced`). 1030 pass.

**Blast radius:** `bin/test-reference-verify`, `lib/gates.py`
(`_EVIDENCE_OPTIONAL_FIELDS`, `verify_coverage`), `bin/prawduct-hook`
(placeholder record), `tests/test_reference_verifier.py`,
`tests/test_verify_coverage_gate.py` (new). Critic (chunk mode): 0 blocking,
1 warning (stale `_looks_like_python` docstring — fixed), 1 note
(informational line now echoes `coverage_level` — adopted).

## 2026-06-09: work-model probe precision — frequency floor, firing threshold, widened corpus

<!-- prawduct: chunks=2 | type=fix | release=v2.1.0 | status=shipped | scope=review-fixes -->

**Why:** The work-model probe (terms-not-in-artifacts tripwire) fired on
ordinary prompts — acknowledgments, questions, noun-homographs ("the build
failed"), contractions — eroding trust in tripwire #1. Four false-positive
prompt classes observed live 2026-06-09.

**What:** Three precision levers: a common-English frequency floor (top-4,000
of the google-10000-english list — the observed false-positive *efficiency*
ranks #3283, forcing the cutoff; 30KB accepted, provenance + license posture
documented in `lib/common_words.py`), a firing threshold, and a widened
artifact corpus. Two extra precision bugs found and fixed during build:
contraction tokens minting orphan non-words ("let's" → "let'"), and
requirement verbs reporting themselves as the orphan ("extend X" flagging
*extend*). All four observed false-positive prompt classes verified silent
live against this repo's hook; "add OAuth login to the settings page" still
fires.

**Blast radius:** `bin/prawduct-hook` (probe), `lib/common_words.py` (new),
`tests/` (+14, 1051 pass). Critic (chunk mode ×2): pass, then 1 warning +
2 notes, all resolved (count drift, sentence-boundary determiner reset,
wordlist license posture).

## 2026-06-09: review-gate soundness — PR doc-only protected paths + Critic marker ordering

<!-- prawduct: chunks=3 | type=fix | release=v2.1.0 | status=shipped | scope=review-fixes -->

**Why:** PR-5K8D: `check-pr-doc-only` treated `skills/*.md` as docs, so
governance-logic changes could skip the independent PR reviewer — the only
remaining PR-boundary gate-skip path after the trivial fast-path was retired.
CRT-6F2N: the critic SKILL ran `critic-begin` before the designer-handoff
early exit, leaving a `.critic-active` marker (blocking `clear`) for up to
its 30-min TTL on a review that never happened.

**What:** Extracted `protected_path_violation()` from the trivial gate's
bound list (`_TRIVIAL_PROTECTED_PATHS`: `skills/`, `methodology/`,
`templates/`, root `CLAUDE.md`) and consulted it in the PR doc-only gate — a
`skills/*.md` PR now exits 1 `not-doc-only`; nested `foo/CLAUDE.md` stays
doc-only (exact-match semantics preserved). Stop-hook Gate 3 inherits the
tightened bound through the shared helper; fails closed. Moved the
designer-handoff early exit BEFORE `critic-begin` in the critic SKILL step 1,
pinned by a prose-ordering test.

**Blast radius:** `lib/buildplan_refs.py` (`protected_path_violation`),
`lib/coverage.py` (PR doc-only gate), `skills/critic/SKILL.md` (step
ordering), `tests/` (+7, 1058 pass). Critic (chunk mode): 1 blocking (a
placeholder path in the build plan's own Tests bullet failed
verify-chunk-refs — fixed), 1 note (accepted with rationale). Both backlog
items shipped/archived via `/prawduct:backlog`.

## 2026-06-09: hot-path correctness fixes (core.py depth, Gate 3 network call, porcelain parsing)

<!-- prawduct: chunks=1 | type=fix | release=v2.1.0 | status=shipped | scope=review-fixes -->

**Why:** Three verified bugs from the 2026-06-09 full-framework review, all on
hooks hot paths. (1) `lib/core.py`'s `FRAMEWORK_DIR = parent.parent.parent` was a
byte-parity holdover from the retired file-sync three-level tools layout — from
top-level `lib/` it resolved one level ABOVE the plugin root, so `TEMPLATES_DIR`
pointed at a nonexistent path and `PRAWDUCT_VERSION` silently read `"dev"` (the
Chunk-14 Critic had called this "inert"; learnings.md already documents why that
verdict didn't hold). (2) The stop-hook's Gate 3 ran `gh pr list` — a
300-800ms network call, 15s timeout worst case — on EVERY turn-end of any
feature-branch session, even with zero session changes, because its only guard
was `not doc_only` and `doc_only` is False when `has_changes` is False. (3) All
three porcelain parsers in `lib/gitstate.py` used `line.split()[-1]`, which
mangles git-quoted space-paths (` M "my doc.md"` → `doc.md"`) and renames — a
doc-only session touching a space-path was falsely blocked by the
Critic/reflection gates.

**What:** Fixed the `FRAMEWORK_DIR` depth and removed `init_product.py`'s
now-dead resolution workaround (it routes through `core` again). Gate 3 now
short-circuits on `not has_changes` (merge-time enforcement stays in
`/prawduct:pr`). Added shared `gitstate.parse_porcelain_line` (quoted paths,
renames; caveats documented), adopted at all three gitstate sites AND the
trivial-gate's previously-duplicated inline parse in `lib/gates.py`; dropped the
whole-output `.strip()` that corrupted the first porcelain line's fixed-offset
status; added the corrupted-baseline guard `_get_session_changed_files` was
missing. Synced `pyproject.toml` 2.0.15→2.0.17. Renegotiated the Gate 3 test
contract in the open (the old tests pinned the always-probe behavior with empty
status; they now carry a code diff, and a recording-mock test pins the ABSENCE
of the `gh` call on a no-change session — 0.29s wall empirically). 17 new
regression tests; 1037 pass.

**Blast radius:** `lib/core.py`, `lib/init_product.py`, `lib/gitstate.py`,
`lib/gates.py`, `bin/prawduct-hook` (Gate 3 condition), `pyproject.toml`,
`tests/test_gitstate_porcelain.py` (new), `tests/test_plugin_init.py`,
`tests/test_pr_reviewer.py`. Critic (final + 2× verify-resolutions) caught the
plan's own `active_build_plan` pointer mis-resolution — fixed in
`.prawduct/project-state.yaml` (pointer is `.prawduct/`-relative).

## 2026-06-08: register the missing legacy-backlog-format advisory probe

<!-- prawduct: chunks=01 | type=fix | release=v2.0.17 | status=shipped | scope=legacy-backlog-format-probe -->

**Why:** A repo that adopted a new prawduct version with an **unmigrated backlog**
got **no advisory** nudging `/prawduct:backlog migrate`. Root cause:
`lib/backlog_probes.py::register()` registered three probes
(`external-backlog-detected`, `legacy-section-schema`, `backlog-overdue-grooming`)
but **not** `legacy-backlog-format` — the *primary* probe whose action is
`/prawduct:backlog migrate` and whose resolution is `backlog_format_version: 2`.
That probe was the single **production** probe shipped in framework v1.7.0
(`tools/lib/backlog_probes.py::legacy_backlog_format_probe`). M4 (v2.0.3) deleted
the file-sync `tools/lib/backlog_probes.py` with the engine; the v0.3 backlog
rework (v2.0.15) built a *new* plugin-native module scoped to `[BKL-2F7K]` — "ship
the three *remaining* §8.2 probes" — a framing that silently assumed the primary
probe still existed. It didn't, so it was registered nowhere. The roster itself was
alive (the grooming probe fires in real briefings), which is exactly why the gap
looked fine — the channel worked, one member was just missing. This is the second
chapter of the M4 advisory-excision saga (learning #206 re-homed the
*infrastructure*; this restores the *member* it was always about).

**What:** Re-port `probe_legacy_backlog_format` faithfully (trigger floor: `>5`
items none carrying a `[PFX-XXXX]` id; partial-migration guard: any structured id
stands the trigger down; count-independent evidence; `priority="info"`) using
`parse_backlog`, which already excludes HTML-comment / code-fence bullets; register
it in `register()`. Reconcile the two stale artifacts that documented it as absent
(the `lib/advisory_store.py` "roster is empty" comment and two
`skills/backlog/SKILL.md` notes). New `TestLegacyBacklogFormatProbe` + a
**registered-roster** end-to-end nudge test (the gap was *registration*, so the
regression drives `register()` + `run_all_probes`, not the probe in isolation).

**Blast radius:** `lib/backlog_probes.py` (+probe +register), `lib/advisory_store.py`
(comment), `skills/backlog/SKILL.md` (two notes), `tests/test_backlog_probes.py`
(+7 tests), `.prawduct/learnings.md` (the spec-roster-vs-open-work-list lesson).
1020 pass. Merged to develop via #85.

## 2026-06-08: retire the PR-boundary trivial fast-path (unsound fileset-as-detector skip-gate)

<!-- prawduct: chunks=01 | type=fix | release=v2.0.17 | status=shipped | scope=retire-pr-trivial-fast-path -->

**Why:** The PR-boundary trivial fast-path (`check-pr-trivial` /
`_pr_diff_is_trivial`) decided trivial-eligibility from the **fileset alone** —
every commit on `merge-base..HEAD` clearing the `Type: trivial` path bounds — with
**no link to any `Type: trivial` declaration**. Exit 0 made `/prawduct:pr` skip
**both** the cumulative-Critic gate and the independent PR reviewer. So a
substantial multi-chunk **feature** that only modified existing files (the common
case) was reported `trivial` and skipped the two core review gates. The fileset
bounds were designed to *enforce* a per-chunk declaration (the stop hook checks them
only when `chunk_type == "trivial"`), not to *detect* triviality at the bundle
boundary — a necessary condition standing in for a sufficient one. And the fast-path
shipped with **zero** test coverage at the PR boundary, which is why it slipped: a
skip-gate (a gate whose job is to waive other gates) needs the *most* adversarial
coverage, not the least.

**What:** Retire the fast-path entirely (user-chosen over gating it on the
declaration). Remove `_pr_diff_is_trivial` + `check_pr_trivial` (`lib/coverage.py`),
`cmd_check_pr_trivial` + dispatch + usage token + the stop-hook Gate-3
`pr_is_trivial` branch (`bin/prawduct-hook`) — only a **doc-only** PR is
evidence-exempt now — and Step 1c + the gate-summary bullet + the `allowed-tools`
entry (`skills/pr/SKILL.md`); reconcile the reviewer's own
`skills/pr/review-protocol.md` "You may be skipped" section to one fast-path; re-anchor
the co-consumer doc-comments (`lib/gates.py`, `lib/buildplan_refs.py`). New
regression test: a fileset-eligible code PR now BLOCKS at Gate 3 for missing review
evidence (the test the retired fast-path never had). The sound **doc-only**
fast-path and the **chunk-level `Type: trivial`** enforcement are untouched.

**Blast radius:** `lib/coverage.py`, `bin/prawduct-hook`, `skills/pr/SKILL.md`,
`skills/pr/review-protocol.md`, `lib/gates.py`, `lib/buildplan_refs.py`,
`tests/test_pr_reviewer.py` (+regression test). 1013 pass at merge. Surfaced as an
incoming bug from `../scriob`. Merged to develop via #84.

## 2026-06-08: `/backlog migrate` refreshes the schema legend, not just item metadata

<!-- prawduct: type=fix | release=v2.0.16 | status=shipped | scope=backlog-legend-refresh -->

**Why:** Adopting a new backlog format field (v2.0.15's `stage:`/`refs:`/`accepted-by:`) has **two**
propagation surfaces that drift independently — the per-item backfill (triage/`migrate`) and the
file's **schema legend** (the `<!-- … -->` header comment). The legend is authored **once** at
scaffold time from `templates/backlog.md` and never re-applied, so a repo that adopts a field ends
up with backfilled items behind a legend that never documents them (a reader hits `stage: ready`
with no key). Surfaced by `../scriob`, which backfilled `stage:` during grooming but had to
hand-add `accepted-by`/`refs:` to its legend afterward.

**What:** `/backlog migrate` gains **step 4c — Legend refresh**: reconcile the header legend to the
current canonical field set (the fields in "The format you operate on"). **Additive &
non-destructive** — fill any missing canonical-field description; never remove a repo's local
extension (e.g. a `kind:` facet); idempotent; runs even when there are no legacy items (like the
strikeout sweep). Threaded through migrate completion (step 5) + report (step 6) and the triage
adoption note. Also fixed the `SKILL.md` optional-fields **enumeration**, which listed
`accepted-by:` but omitted `stage:` and `refs:` (both documented in their own bullets — the list
just lagged the schema). `documentation/backlog-system-requirements.md` §8.4 updated to match.

**Blast radius:** `skills/backlog/SKILL.md` (migrate step 4c + enumeration), `documentation/
backlog-system-requirements.md` (§8.4), `.prawduct/learnings.md` (the scaffold-only-legend lesson).
Docs/skill-prose only — no code, no test change (1012 pass).

## 2026-06-08: infer-critic-mode derives chunk progress from git on a views-enabled branch (CRT-7B4M)

<!-- prawduct: chunks=01 | type=fix | release=v2.0.16 | status=shipped | scope=critic-mode-branch-fix -->

**Why:** On a `views_enabled` feature branch the build-plan `## Status` checkboxes are a *derived
view* that only flips at release, so they stay all-`[ ]` during development. `infer-critic-mode`
read the current chunk from those checkboxes — so `_current_chunk_id_from_status` always returned
the first chunk and `_count_build_plan_chunks` always reported `complete=0`. The plan-override then
read **Chunk 01's** `Critic mode:` for *every* chunk, and rule-3's last-chunk detection could never
fire — the Critic ran the wrong mode on a views-enabled branch (the common case).

**What:** When the Status checkboxes are an unflipped derived view (`views_enabled` true, HEAD ahead
of a resolved base branch), `lib/critic_mode.py` now derives committed-chunk progress from **git** —
`_committed_chunk_ids` (chunk ids referenced by `Chunk <n>` in commit subjects on `base..HEAD`),
`_chunk_ids_in_status_order`, and `_git_aware_progress` returning `(complete, current_chunk_id)`;
`_current_chunk_critic_mode` resolves the current chunk via this (falling back to the first `[ ]`),
and `_rule_final_fires` consumes the git-aware `complete`. Degrades to the existing checkbox
behavior whenever the git signal doesn't apply (no views, no base, not ahead, no chunk-referencing
commits) — never worse than before. Critic WARNING-1 fix (scope-expanded, deliberate): replaced the
main-first `_detect_base_branch` with the canonical `_resolve_base_branch` (honors `base_branch:`)
at both call sites and removed the duplicate.

**Blast radius:** `lib/critic_mode.py` (+201/-49); `tests/test_critic_mode_inference.py` (+7,
`TestBranchProgressCRT7B4M` incl. a gitflow-divergence case); `skills/critic/SKILL.md`,
`skills/critic/review-cycle.md` (doc touch). Merged to develop via #82, released in v2.0.16.
1012 tests pass.

## 2026-06-08: Backlog rework — claims, lifecycle stage, parser substrate, probes, triage (v0.3)

<!-- prawduct: chunks=01,02,03,04,05,06,07,08,09,10 | type=feature | release=v2.0.15 | status=shipped | scope=backlog-rework -->

**Why:** Real multi-agent use in `../scriob` exposed five backlog failures (no claim/lock for
concurrent work; completed work left stale; strikethrough instead of archive; vague items flowing
straight to code with no requirements; no codified triage) plus the meta-failure that the backlog
sat *beside* the work cycle — nothing routed agents to `/prawduct:backlog`, so they hand-edited.
Root causes: not-wired-in, deferred-nudges, format-models-state-not-claim/stage, no-triage-method
(requirements `documentation/backlog-system-requirements.md` v0.3 §0).

**What (10 chunks):** (1) `lib/backlog.py` — a structured parser substrate mirroring `lib/views.py`
(the lean core had none); the briefing's hand-rolled count now derives through it. (2) `accepted-by`
soft claim (no auto-expiry, D10) — `pick`/`list` exclude claimed items. (3) `stage:` lifecycle
(idea→research→requirements→design→ready, D11) — `pick` routes early-/unstaged items to discovery,
not code, closing the requirements-precede-code hole (Principle 6). (4) `refs:` doc-links,
`/backlog dedup`, a Triage method section. (5) Critic C-B1–C-B4 + PR-reviewer R-1/R-2 backlog
checks (flag, never infer — D4). (6) the three §8.2 probes (external-backlog, legacy-section,
overdue-grooming). (7) archive discipline + strikeout-cleanup sweep + archive-split + janitor
Step 2.5 Backlog Health. (8) `/backlog import` + doctor external-file health check. (9) workflow
wiring — the session digest (universal carrier) + building/reflection/planning/discovery +
build-plan template route through the skill (route+flag, not gate — D13). (10) this reconciliation.

**Design constraints (D10–D14):** claims don't auto-expire (stale claim = out-of-scope process
problem); migration/cleanup = triage (additive fields, no separate subsystem); a structured parser
is the substrate (D12); wiring is route+flag not hard-gate (D13); **derived counts are never
persisted — always re-derived on read (D14)** (only the `backlog_last_groomed_at` timestamp +
`backlog_format_version` are stored). §12 non-goal amended to allow the soft claim (not PM assignment).

**Blast radius:** new `lib/backlog.py`, `lib/backlog_probes.py`; `lib/briefing.py` rewired;
`bin/prawduct-hook` probe registration; `skills/backlog/SKILL.md`, `skills/critic/review-cycle.md`,
`skills/pr/review-protocol.md`, `skills/janitor/SKILL.md`, `skills/doctor/SKILL.md`;
`methodology/{building,reflection,planning,discovery,session-digest}.md`; `templates/{backlog,build-plan}.md`.
New tests: `test_backlog_parser.py` (23), `test_backlog_probes.py` (16), plus presence/parity
assertions across digest/methodology/pr-reviewer suites. 1005 tests pass; Critic per chunk
(0 blocking throughout). Subsumes v0.2-deferred BKL-2F7K/3R8P/5H9M/1V8J/6L3Q, CRT-3K9P, JNT-7T1W.

## 2026-06-07: critic-active session guard — `clear` refuses to mutate a session under review (CRT-3X9D)

<!-- prawduct: chunks=1 | type=fix | release=v2.0.14 | status=shipped | scope=critic-session-guard -->

**Why:** The Critic is documented (CLAUDE.md, `skills/critic/SKILL.md`) as structurally unable to
run executables — review by code analysis only. But the coordinator pattern dispatches review
subagents via the `Agent` tool, and Agent-spawned subagents do NOT inherit the skill's restricted
`allowed-tools`; they run with the session's default Bash latitude (here: `Bash(python3:*)`,
`Bash(bash:*)`). During the STH-9V4K ch.7 review a subagent ran `prawduct-hook clear`, which is
destructive — it archived/deleted the builder's `.session-reflected`, rewrote `.session-start`
(making fresh test evidence read "stale"), and recaptured the git baseline. An independent reviewer
clobbered the very session it was reviewing; the builder had to hand-restore state. The tool
restriction the docs promised was prose, not structure.

**What:** Enforce the real invariant — *an independent reviewer must never mutate the session it is
reviewing* — at the mutation site rather than relying on a tool restriction that doesn't bind
subagents. New `lib/critic_marker.py` manages a `.prawduct/.critic-active` marker (`write_marker` /
`clear_marker` / `review_active`, TTL `CRITIC_ACTIVE_TTL_SECONDS = 1800`). Two new hook subcommands —
`critic-begin` (writes the marker, run at Critic step 1) and `critic-end` (removes it, step 8) —
bracket a review; both are added to the Critic skill's `allowed-tools`. `cmd_clear` gains a guard at
the top (before any mutation): a bare `clear` with an active marker refuses (exit 2) with an
actionable override; the genuine SessionStart hook is rerouted to `clear --session-start` (always
proceeds + sweeps the marker), and `--force` is the operator override. `.critic-active` added to
`GITIGNORE_ENTRIES`, the inline `_SESSION_GITIGNORED_PATHS` mirror, and `.gitignore`. CLAUDE.md +
SKILL.md prose updated to describe the backstop honestly (the old "structural constraint" claim is
now "directed not to … + a mutation-site guard").

**Resilience (the design priority).** A crashed/hung Critic that never reaches `critic-end` must not
permanently brick `clear`. Three independent self-corrections, modeled on the waiver escape-hatch:
(1) **TTL auto-expiry** — a marker older than 30 min stops counting as active and is swept on read;
(2) **session-start sweep** — the next real session start deletes any marker; (3) **explicit
override** — the refusal message names `rm .prawduct/.critic-active` and `clear --force`. The guard
also fails OPEN on a lib import error (a broken lib means the Critic can't run, so there's no review
to protect; session start is never blocked). A corrupt/unparseable marker falls back to file mtime,
then to stale — failing toward availability, never toward a permanent block.

**Scope / deferred.** Path B (a dedicated restricted reviewer-agent type so coordinator subagents
genuinely can't invoke `pytest`/`clear`) is deferred as defense-in-depth. `stop` is verified
read-only (no session mutation) and left unguarded. Tests: new `tests/test_critic_session_guard.py`
(15 unit + behavioral cases — refuse-without-mutation, session-start/force/stale/no-marker proceed,
TTL boundary, corrupt-marker mtime fallback, begin/end lifecycle + idempotency); two hook-command
pinning tests updated for `clear --session-start`; `run_plugin_hook` extended to pass argv. 962
passed. Critic `final` (plan-override): no blocking/warning findings.

## 2026-06-07: extract lib/briefing.py — SessionStart briefing + handoff assembly (STH-9V4K ch.7, final)

<!-- prawduct: chunks=7 | type=refactor | release=v2.0.14 | status=shipped | scope=hook-decomp -->

**Why:** The final chunk of the hook decomposition (STH-9V4K). The SessionStart surface — the
content-based staleness scan, the structured session briefing, the subagent briefing, the
cross-`/clear` session handoff, and the previous-session governance check — was the last cohesive
cluster in the monolith and the top of the plan's DAG (`briefing` imports `gitstate`/`gates`/
`buildplan_refs`; nothing imports `briefing`). Extracting it leaves the hook a thin dispatcher
(bootstrap + the parity-pinned inline mirrors + the lazy `lib` accessors + `cmd_*` wrappers +
`cmd_clear`/`cmd_stop`/`main`). The hook drops **2,793 → 1,911 lines** (−882); across the whole
decomposition, **4,942 → 1,911** (−61%).

**What:** New `lib/briefing.py` holds 17 functions moved verbatim — `_extract_dependency_names`,
`staleness_scan`, `_get_product_name`, `_get_current_branch`, `_parse_wip`, `_parse_all_wip_branches`,
`_get_active_work`, `_get_work_in_progress`, `_detect_worktrees`, `_get_other_branch_wip`,
`assemble_session_briefing`, `_extract_critical_rules`, `generate_subagent_briefing`,
`_git_session_commits`, `_summarize_critic_findings`, `generate_session_handoff`,
`_check_previous_session_gates`. (The 18th name the plan listed for ch.7, `_has_active_build_plan_file`,
was already reassigned to `lib/gates` in ch.6 as a gate-used probe.) Sanctioned internal rewrites,
identical in spirit to ch.5/ch.6: `get_prawduct_dir`→`gitstate.get_prawduct_dir`,
`_resolve_build_plan_path`→`core.resolve_build_plan_path` (the canonical twin of the hook's
parity-pinned inline mirror), and the `_gitstate()`/`_gates()`/`_buildplan_refs()` accessor calls →
direct sibling references. The hook keeps `cmd_clear` resident (the inline hot-path SessionStart entry
that orchestrates session-marker hygiene, the advisory probe, and the git baseline) plus a new lazy
`_briefing()` accessor; its five call sites (`staleness_scan` / `assemble_session_briefing` /
`generate_subagent_briefing` / `generate_session_handoff` / `_check_previous_session_gates`) were
rewired to `_briefing().<fn>`.

**Degradation (the chunk's one design decision).** The briefing was deliberately lib-free on the hot
path so session start stayed robust on an incomplete plugin install. Moving it into `lib` adds an
import that can fail. Decision: **no new degradation shim** — each of `cmd_clear`'s five `_briefing()`
call sites is already wrapped in a broad catch, so a `lib.briefing` `ImportError` surfaces at the call
site (not the hook's top level), degrades to a skipped briefing (a stderr NOTE), and the session still
starts (markers + baseline written, returns 0). This is the established ch.2–6 precedent (an import
failure surfaces at the resident call site, never at module top); a minimal-briefing fallback would be
new behavior the behavior-preserving refactor does not call for.

**Tests:** new `tests/test_briefing_extraction.py` — exercises the public surface directly from
`lib.briefing` (the "test the code where it lives" discipline + the coverage preference; no test
referenced these symbols before this chunk) and pins the degradation contract (`cmd_clear` survives a
monkeypatched `_briefing()` `ImportError`: returns 0, writes `.session-start`, skips the briefing
artifact). `test_plugin_runtime.py`'s no-bare-command-forms sweep now scans `lib/briefing` too — the
briefing is the most command-hint-dense surface (the backlog/learnings/advisory hints), so its
`/prawduct:*` strings must stay under the namespacing guard once they leave the hook (closing the
leak-coverage gap the move opens). No symbol repoints were needed (the briefing was tested only
behaviorally, via the `clear` CLI). AST-verified: all 17 functions are byte-identical to the source
after the sanctioned rewrites; a golden compare confirms `assemble_session_briefing` renders
byte-identical output before/after. The PR reviewer then surfaced that the briefing internals had
only ever been exercised through the `clear` integration path, so `tests/test_briefing_functions.py`
adds **57 per-branch characterization tests** (WIP-format detection, worktree porcelain parsing, the
previous-session gate branches, the optional briefing sections, handoff/subagent assembly,
critic-findings summarization) — converting that inherited residual into verified coverage. The same
review caught a now-dead `import re` in the hook (the regex users all moved to `lib/briefing`),
removed in a follow-up. Full suite **947 passed** (884 + 6 extraction + 57 briefing unit tests;
behavior-preserving); `clear`/`stop` smoke-clean via the real CLI through `_briefing()`.

## 2026-06-07: extract lib/gates.py — session-end gate helpers + evidence/critic validators (STH-9V4K ch.6)

<!-- prawduct: chunks=6 | type=refactor | release=v2.0.14 | status=shipped | scope=hook-decomp -->

**Why:** Chunk 6 of the hook decomposition (STH-9V4K) — the gate-decision layer the Stop hook
orchestrates (test-evidence currency + schema validation, critic-findings schema + cumulative /
verify-resolutions gate logic, build-plan chunk counting, trivial/build-plan state probes). Sits atop
`gitstate`/`coverage`/`buildplan_refs` in the DAG; the largest single extraction (the hook drops
**3,785 → 2,793 lines**, −992).

**Scope decided with the user after a dependency scan found a plan contradiction.** Chunk 6's text said
"move the bodies of `cmd_stop` …", but Chunk 7 + design constraint 1 say the hook keeps `cmd_stop`
inline. The scan resolved it: `cmd_stop` uses the hook-resident gate-attribution machinery
(`_gate_attribution`/`_load_gate_registry`/`_plugin_manifest_version`, shared with `cmd_clear`), so
moving its body to `gates` would be a `gates → bin` back-import. User chose **"helpers to gates,
`cmd_stop` stays."**

**What:** New `lib/gates.py` holds 9 gate helpers (`tests_are_current`, `_validate_evidence_schema`,
`_read_gates_waived`, `validate_critic_findings`, `_compute_verify_resolutions_scope`,
`_verify_resolutions_gate_check`, `_count_build_plan_chunks`, `_critic_session_satisfies_gate`,
`_has_build_plan_in_state`) + 9 evidence/critic-mode constants + **reassigned** `_has_active_build_plan_file`
(a gate-used probe nominally listed under ch.7, but it only depends on `buildplan_refs`) and
`_is_trivial_fileset_eligible` + the 4 self-contained gate command bodies, renamed prefix-free as
`test_status` / `validate_evidence` / `check_cumulative_critic` / `verify_coverage` (the two deferred
from ch.5 plus test-status/validate-evidence; hook keeps thin `cmd_*` wrappers via a new lazy
`_gates()` accessor). Sanctioned internal rewrites: `get_prawduct_dir`→`gitstate.get_prawduct_dir`,
`_resolve_build_plan_path`→`core.resolve_build_plan_path`, `_read_bool_yaml_key`→`core.read_bool_yaml_key`,
and accessor calls (`_gitstate()`/`_buildplan_refs()`/`_coverage()`)→sibling imports. **`cmd_stop` and
`cmd_test_evidence` stay resident** (attribution machinery / `_plugin_root` deps), calling the moved
helpers via `_gates()`; the hook's lib-free top level (ch.1 invariant) is preserved. Resident callers
rewired: `cmd_stop`, `_check_previous_session_gates`, `staleness_scan`,
`cmd_compute_verify_resolutions_scope`.

**Tests:** `test_critic_mode_inference.py` repointed (`validate_critic_findings`→`lib.gates`; now-dead
`_load_prawduct_hook` helper removed). `test_plugin_runtime.py`'s no-bare-command-forms test now scans
the runtime command surface (hook + `lib/gates` + `lib/coverage`) instead of only the hook, so a bare
form can't hide in a relocated command body — closing the leak-coverage gap the decomposition opens.
`test_critic_gate_fallthrough.py` / `test_cumulative_gate.py` needed no change (they drive `stop` via
subprocess). Full suite 884 passed (count unchanged — behavior-preserving). AST-verified: the 5 pure
helpers byte-identical to the merge-base hook, the others differ only by the sanctioned rewrites.
`stop`/`test-status`/`validate-evidence`/`verify-coverage`/`check-cumulative-critic` smoke-clean via the
real CLI through `_gates()`.

**Also:** corrected the ch.5 change-log + build-plan hook-size figures (3,757→3,785, −301→−273; the
prior numbers were measured before the accessor + wrappers were re-added).

## 2026-06-07: extract lib/coverage.py — diff-base resolution + PR fast-path gates (STH-9V4K ch.5)

<!-- prawduct: chunks=5 | type=refactor | release=v2.0.14 | status=shipped | scope=hook-decomp -->

**Why:** Chunk 5 of the hook decomposition (STH-9V4K). The diff-base resolution layer (honoring the
`base_branch:` gitflow knob) and the coverage / PR fast-path inspection it feeds sit one layer above
`buildplan_refs` in the plan's DAG (`buildplan_refs ← coverage`). Extracting it continues the
leaf-first walk and removes another cohesive cluster from the monolith.

**What:** New `lib/coverage.py` holds 6 helpers moved **verbatim** + 2 constants + the 2 gates-free PR
fast-path commands: `_git_ref_exists`, `_resolve_base_branch`, `_coverage_resolve_base`,
`_coverage_changed_files`, `_pr_diff_is_doc_only`, `_pr_diff_is_trivial` (+ `_BASE_BRANCH_KEY` /
`_DEFAULT_BASE_CANDIDATES`), and `check_pr_doc_only` / `check_pr_trivial` (the bodies of the former
`cmd_check_pr_doc_only` / `cmd_check_pr_trivial`; hook keeps thin `cmd_*` wrappers delegating via the
new lazy `_coverage()` accessor). Three sanctioned internal rewrites: `_resolve_base_branch` reaches
`read_str_yaml_key` from `lib.core` (the canonical twin of the hook's parity-pinned `_read_str_yaml_key`
mirror); `_pr_diff_is_trivial` calls `buildplan_refs._classify_trivial_change` as a sibling; the two
moved commands drop the `cmd_` prefix (lib entry-point convention, matching `migrate_plugin.run`).
The hook gains the `_coverage()` accessor; its top level stays lib-free (ch.1 isolation invariant —
importing `coverage` pulls in only the light `buildplan_refs`/`gitstate`/`core`). Resident callers
rewired: `cmd_stop` (Gate 3 doc-only/trivial), `cmd_test_evidence`, `cmd_verify_coverage`,
`cmd_resolve_base`. Hook: −273 lines net (4,058 → 3,785).

**Two scope corrections (both validated against the code before building, per Validate-Before-Propagating):**
(1) `cmd_verify_coverage` + `cmd_check_cumulative_critic` bodies were **deferred to Chunk 6** — they
depend on `_validate_evidence_schema` / `validate_critic_findings` / `_CRITIC_MODE_CUMULATIVE` (Chunk-6
`gates` symbols); since the DAG is `coverage ← gates`, moving them now would be a `coverage → gates →
bin` back-import. They stay resident (calling the moved helpers via `_coverage()`) and move with
`gates`. (2) `_read_bool_yaml_key` **stays in the hook** — the plan listed it to move, but it is a
parity-pinned inline import-light mirror of `lib.core.read_bool_yaml_key` (`TestBoolKeyCallSiteParity`),
the same class as `_read_str_yaml_key`; the code's explicit mirror contract overrides the plan text.

**Tests:** `test_views.py` unchanged (its `_read_bool_yaml_key` parity test still pins the hook
mirror — corrected from the plan's "repoint test_views.py"). `test_plugin_runtime.py` source-inspection
repointed: the `"def _resolve_base_branch(" in src` hook assertion → `"_coverage()._resolve_base_branch("
in src` (the resolver moved; the wrapper delegates). The CLI behavioral tests (`resolve-base`,
`check-pr-doc-only`/`-trivial` via subprocess) are unchanged and exercise the move end-to-end. Full
suite 884 passed (count unchanged — behavior-preserving). AST-verified vs the merge-base hook: 6 of
the 8 moved bodies are byte-identical (the 4 pure helpers + the 2 PR commands, whose only change is
the `cmd_` prefix drop on their def line); the remaining 2 (`_resolve_base_branch`,
`_pr_diff_is_trivial`) differ only by the sanctioned internal rewrites.

## 2026-06-07: extract lib/compliance.py — session-end compliance canary + file classifiers (STH-9V4K ch.4)

<!-- prawduct: chunks=4 | type=refactor | release=v2.0.14 | status=shipped | scope=hook-decomp -->

**Why:** Chunk 4 of the hook decomposition (STH-9V4K). The session-end compliance canary — the
lightweight failure-detection pass `cmd_stop` runs (code-without-tests, dependency-without-manifest,
broad exception handling, reason-less waivers) — is its own cohesive concern sitting one layer up from
the ch.2 `gitstate` leaf. Extracting it continues the leaf-first DAG walk
(`gitstate ← compliance`) and removes another self-contained cluster from the monolith.

**What:** New `lib/compliance.py` holds 7 functions moved **verbatim**: `compliance_canary`,
`_check_broad_exceptions`, `_check_invalid_waivers`, `_waivers_module`, plus the file classifiers
`_is_source_file` / `_is_test_file` / `_is_dependency_file` (their only caller is the canary). Two
sanctioned internal rewrites, both forced by the lib→bin no-back-import rule: `compliance_canary`
reaches the changed-file probe + prawduct-dir helper via `from . import gitstate`
(`gitstate._get_session_changed_files` / `gitstate.get_prawduct_dir`, replacing the hook's
`_gitstate().…` / inline `get_prawduct_dir`), and `_waivers_module` drops the now-redundant
`_plugin_root()` sys.path seeding for a relative `from . import waivers` (the lib package is already
importable once `compliance` loads). The fail-open posture is preserved exactly — `_waivers_module`
still returns `None` on import failure so the canary emits no waiver-dependent finding. The hook gains
a lazy `_compliance()` accessor (mirrors `_gitstate()`) and rewires the single `cmd_stop` call site to
`_compliance().compliance_canary(...)`; its top level stays lib-free (ch.1 isolation invariant
preserved — importing `compliance` pulls in only `gitstate`, with `waivers` still lazy).

**Tests:** `test_waivers.py` repointed to `from lib import compliance` for the two canary helpers it
exercises (`_check_broad_exceptions`, `_check_invalid_waivers`); the now-dead `SourceFileLoader` hook
shim and its `importlib` imports were removed (the module no longer needs the hook). Full suite 884
passed (count unchanged — behavior-preserving); the `stop` canary path is smoke-clean via the hook's
real `_compliance()` accessor (broad-except flags only the unwaived file; waiver honored end-to-end).
AST-verified: the 5 pure-move functions are byte-identical to HEAD; the 2 rewritten ones differ only
by the sanctioned rewrites above. Hook: −168 lines net (4,226 → 4,058).

## 2026-06-07: extract lib/buildplan_refs.py — build-plan ref parsing + trivial classification (STH-9V4K ch.3)

<!-- prawduct: chunks=3 | type=refactor | release=v2.0.14 | status=shipped | scope=hook-decomp -->

**Why:** Chunk 3 of the hook decomposition (STH-9V4K). The build-plan-parsing cluster (chunk-ref /
`Type:` / `Trivial because:` parsers + the `Type: trivial` file-set classifier) is the next layer up
from the ch.2 `gitstate` leaf. Moving it out also performs the **cycle-break** the plan's dependency
analysis identified (constraint 2): `_parse_build_plan_status` was mis-homed in the briefing cluster
(it is build-plan parsing, not briefing assembly); reassigning it here turns the six concern clusters
into an acyclic DAG (`gitstate ← buildplan_refs ← coverage ← gates ← briefing`).

**What:** New `lib/buildplan_refs.py` (524 lines) holds 8 functions + 6 constants moved **verbatim**:
`_parse_build_plan_status`, `_looks_like_file_path`, `_parse_build_plan_chunk_refs`,
`_parse_build_plan_chunk_type`, `_parse_build_plan_chunk_trivial_rationale`, `_classify_trivial_change`,
`_current_chunk_id_from_status`, `_verify_chunk_refs`; constants `_BUILD_PLAN_PATH_RE` /
`_BUILD_PLAN_NEW_QUALIFIER_RE` / `_BUILD_PLAN_TYPE_RE` / `_BUILD_PLAN_ALLOWED_TYPES` /
`_BUILD_PLAN_TRIVIAL_RATIONALE_RE` / `_TRIVIAL_PROTECTED_PATHS`. Two sanctioned internal rewrites: the
module reaches the canonical resolver via `from .core import resolve_build_plan_path` (the established
lib idiom — `critic_mode`/`views` do the same; avoids a third copy of the hook's parity-pinned inline
mirror, which stays in the hook for its import-light hot path) and `_is_metadata_path` via
`from . import gitstate`. The hook gains a lazy `_buildplan_refs()` accessor (mirrors `_gitstate()`)
and rewires its 11 resident call sites; its top level stays lib-free (ch.1 isolation invariant
preserved). `_count_build_plan_chunks` / `_pr_diff_is_trivial` / `_is_trivial_fileset_eligible` /
`cmd_verify_chunk_refs` stay in the hook (Chunk 5–6 work) and now delegate via the accessor.

**Tests:** `test_build_plan_resolution.py` (`_parse_build_plan_chunk_refs`, `_verify_chunk_refs`) and
`test_trivial_fileset_gate.py` (`_classify_trivial_change`, `_TRIVIAL_PROTECTED_PATHS`) repointed to
`from lib import buildplan_refs` — tested where the code now lives, assertions unchanged. One stale
doc pointer fixed (the chunk-heading-rule location in `test_build_plan_resolution.py`). Full suite 884
passed (count unchanged — behavior-preserving); `verify-chunk-refs`/`clear`/`stop` smoke-clean via the
real CLI (the stop `trivial-declaration` gate fired end-to-end). Critic (chunk): 0 findings —
AST-verified all 8 moved bodies byte-identical to HEAD + 6 constants value-identical. Hook: −464 lines
net (4,690 → 4,226). Enabled follow-up STH-2K8R filed (critic_mode could now consume buildplan_refs
instead of mirroring it).

## 2026-06-07: extract lib/gitstate.py — read-only git/state probes (STH-9V4K ch.2)

<!-- prawduct: chunks=2 | type=refactor | release=v2.0.14 | status=shipped | scope=hook-decomp -->

**Why:** Chunk 2 of the hook decomposition (STH-9V4K) — extract the leaf of the dependency DAG. The
read-only git/state probes are the most depended-upon cluster (briefing, gates, compliance,
buildplan_refs all sit on them), so they move first; every later extraction then imports from an
already-extracted `lib/gitstate` rather than reaching back into the hook (a lib→bin back-import).

**What:** New `lib/gitstate.py` (leaf, stdlib-only) holds 13 probes + 3 constants moved **verbatim**
(`git_status_output`, `git_has_changes`/`_has_session_changes`/`_has_code_changes`,
`_session_changes_are_doc_only`, `_is_metadata_path`, `_is_framework_tooling`, `_has_product_code`,
`_has_product_definition_work`, `_discovery_uncaptured`, `_read_advisory_store`, `_git_head_sha`,
`_get_session_changed_files`; constants `_METADATA_PREFIXES`/`_PRODUCT_CODE_SUFFIXES`/`_DOC_ROOTS`).
A local `get_prawduct_dir` keeps the module self-contained. The hook gains a lazy `_gitstate()`
accessor (mirrors `_waivers_module()`) and rewires its 19 resident call sites to `_gitstate().<fn>`;
its top level stays lib-free (invariant preserved). The session-start git *mutation*
(`_untrack_session_files` + the parity-pinned `_SESSION_GITIGNORED_PATHS` mirror) stays in the hook —
gitstate is read-only probes only.

**Tests:** `test_discovery_capture_nudge.py` repointed to `from lib import gitstate` for the 3 probes
it exercises (`cmd_clear` stays on `_hook`). Full suite 884 passed; `clear`/`stop` hot paths
smoke-clean via the real CLI. Critic (chunk): 0 findings — AST-verified all 16 moved symbols
byte-identical to HEAD. Hook: −252 lines net (4,942 → 4,690).

## 2026-06-07: lib/__init__.py lazy imports — enabling the hook decomposition (STH-9V4K ch.1)

<!-- prawduct: chunks=1 | type=refactor | release=v2.0.14 | status=shipped | scope=hook-decomp -->

**Why:** `bin/prawduct-hook` is deliberately lib-independent at its top level (every `lib` import is
lazy + `try/except ImportError`-guarded; the SessionStart briefing + the whole `cmd_stop` gate run
inline) "so the hot path stays robust even on an incomplete plugin install." But `lib/__init__.py`
*eager-imported* the heavy modules (advisory_store, views, operator_verification, critic_mode,
audit_learnings_cmd) to provide a flat API, so `from lib import <anything>` cost ~34ms and coupled
session start to every heavy module's importability. That blocks extracting the briefing/gate logic
into `lib/` (STH-9V4K) without regressing the invariant — the enabling first chunk of the
decomposition.

**What:** Replaced the eager `from .X import (...)` re-export blocks with a PEP-562 module-level
`__getattr__` backed by a `_FLATTENED_EXPORTS` name→submodule map (50 names) + `_SUBMODULE_EXPORTS`
({views, waivers}), caching each resolved name into globals on first access. The flat API is
preserved exactly (`from lib import infer_mode`, `lib.GITIGNORE_ENTRIES`, …); submodule imports
(`from lib import views`, `from lib.advisory_store import run_sync_advisories`) resolve natively.
Now `from lib import <leaf>` loads only that submodule (~1ms, isolated): a syntax error in `views.py`
no longer breaks an unrelated `from lib import gitstate`.

**Tests:** `tests/test_lib_lazy_imports.py` (8) — isolation pinned in a fresh-interpreter subprocess
(`import lib` / `import lib.core` / touching a flat name drag in zero heavy modules), and the flat API
hard-coded as a contract (a dropped export fails the test). Full suite 884 passed. Critic (chunk): 0
blocking / 0 warning / 0 note.

## 2026-06-06: verify-chunk-refs skips glob patterns written as prose (BLD-2R9X)

<!-- prawduct: type=bugfix | release=v2.0.14 | status=shipped -->
<!-- Merged to develop (release-pending) via #73. Flip status=merged → status=shipped and add
     release=vX.Y.Z at the develop→main release. -->

**Why:** The chunk-ref verifier's path detector treated any backticked token containing `/` as a
literal file to existence-check, so a glob written in prose (e.g. a Tests bullet's
`docs/requirements/*.md`) was captured and reported `missing-ref: … file does not exist` — advisory
noise on an active build plan. (BLD-2R9X)

**Fix:** `_looks_like_file_path` (`bin/prawduct-hook`, the single helper the chunk-ref parser consults)
now returns False for any token carrying a shell-glob metacharacter (`*`, `?`, `[`). A literal source
path never contains one, so this skips globs without risking real paths. Same parser family as the
shipped BLD-8F2Q (`path::symbol` over-match); symbol/backlog-ref verification stays deferred
(BLD-5V8F).

**Tests:** 4 regression tests in `tests/test_build_plan_resolution.py::TestVerifyChunkRefsGlobPaths`
(each glob metacharacter + the per-token case where a real path on the same line is still captured).
875 passed.

## 2026-06-06: /prawduct:pr redirects a release promotion to the release process (REL-8K3M)

<!-- prawduct: type=bugfix | release=v2.0.14 | status=shipped -->
<!-- Merged to develop (release-pending) via #72. Flip status=merged → status=shipped and add
     release=vX.Y.Z at the develop→main release. -->

**Why:** The `/prawduct:pr` skill is shaped for **feature→`develop`** PRs, but a contributor
naturally reaches for it to "ship" a release — and lands in Step 2's cumulative-Critic gate
(`check-cumulative-critic`), which correctly refuses because release-prep necessarily touches
non-`.md` version files (version strings + `regen-views`-regenerated `scope_rollups`) that CRT-7M2D's
docs-only allowance doesn't cover. The gate isn't broken — it's being run in a context it doesn't
govern. Surfaced firsthand during the v2.0.13 (work-model) release. (REL-8K3M)

**Fix (a + b — no gate-logic change):**
- `skills/pr/SKILL.md` — a **release-promotion guard** in Context Detection: when the current branch
  is the integration base (`develop`) or release surface (`main`/`master`) rather than a feature
  branch, the skill recognizes a release/integration context and **redirects to
  `docs/release-process.md`** instead of running the feature-PR gates. Stops the false-positive at the
  source.
- `docs/release-process.md` — a new "`/prawduct:pr` is not the release vehicle" section documenting
  that a `check-cumulative-critic` exit-1 during release-prep is **expected and benign** — neither a
  gate to re-satisfy (the CRT-7M2D treadmill) nor a waiver case (the gate IS satisfiable in a feature
  context; it simply isn't the release's gate), since the stop hook also stands down once
  `active_build_plan` is cleared.

**Rejected (c):** broadening the CRT-7M2D allowance to treat version/derived-view files as
non-substantive — it would weaken a correct, global gate for *every* repo's feature PRs to patch a
context-misuse (a feature PR bumping a version would skip cumulative review of that change).

**Tests:** 2 guards in `tests/test_pr_reviewer.py::TestPrReviewSkillContent` (the skill redirect; the
release-doc benign-exit note). 871 passed.

## 2026-06-06: Work model — catch undocumented requirements (shipped v2.0.13)

<!-- prawduct: chunks=1,2,3 | type=feature | release=v2.0.13 | status=shipped | scope=work-model -->

**Why:** Prawduct policed requirement *loss* (Complete Delivery) but not requirement *absence* — a
fluent agent could design a new domain model in conversation and flow it into code with no
requirements artifact, and nothing stopped it. This closes the asymmetry with an external,
deterministic catch (motivated by a real session — the scriob fact/belief-modeling thrash).

**What's built (chunks 1–3):**
- `lib/work_model_index.py` (NEW) — pure catch logic: a conservative vocabulary index (artifact
  headings/bold + optional `vocabulary:` frontmatter) and an orphan-term diff that surfaces salient
  prompt terms no governing artifact covers. Keystone proven by a real-scriob replay test; false-
  positive noise characterized honestly (the gate for the deferred LLM classifier).
- `bin/prawduct-hook` `build-index` + `user-prompt-submit` (NEW) + `hooks/hooks.json` — a
  UserPromptSubmit hook injects a pre-turn nudge on orphan terms; SessionStart warms the per-repo
  index (`.prawduct/.work-model-index.json`, gitignored). Fail-soft, `.prawduct/`-gated.
- Principle 6 gains its mirror clause (principles.md + CLAUDE.md); building.md gains the "A
  Requirement Surfaced Mid-Build" tripwire callout; discovery.md gets a scope-expansion sentence; the
  session digest's drop-requirement rule is now bidirectional.

**Deferred (confidence-gated, → backlog):** the LLM-in-hook concept classifier, the PreToolUse
parent-coverage floor, the Critic pre-code plan-review, and the parent-map injection (B2) — each earns
its way in with usage evidence. Design lineage + two independent reviews: `docs/work-model*.md`.

**Release:** shipped in **v2.0.13** (develop→main promotion, 2026-06-06). Merged to develop via #71.

## 2026-06-05: /prawduct:repo-disable — turn the plugin off per-repo (shipped v2.0.12)

<!-- prawduct: type=feature | release=v2.0.12 | status=shipped -->

**Why:** The plugin installs at **user** scope, so its commands, hooks, and banner load in every
repo the user opens. v2.0.11 silenced the SessionStart *hooks* in repos with no `.prawduct/`, but
the `/prawduct:*` commands and the version banner still appear everywhere. The native lever to turn
the plugin OFF in one repo (a project/local-scope `enabledPlugins` override that beats the
user-scope enable) required hand-editing JSON. This ships a guided, safe command for it.

**Design decision — disable only, no enable:** a disabled plugin's own skills do not load, so a
`/prawduct:repo-enable` skill could never run in the repo where it's needed (verified against the
Claude Code plugin model). Re-enabling is therefore a documented manual edit (set the value back to
`true` / delete the key, then `/reload-plugins`) — the disable skill and the applied CLI output both
spell out the exact steps. Building both commands as first requested would have shipped a dead one.

**What shipped (via #69 → develop, then v2.0.12):**
- `lib/repo_toggle.py` (NEW) — `set_repo_disabled(project_dir, *, local, apply)`: idempotent shallow
  merge of `"enabledPlugins": {"prawduct@prawduct": false}` into `.claude/settings.json` (committed)
  or `.claude/settings.local.json` (`--local`, Claude-Code-auto-gitignored), **preserving every
  other key** (permissions, env, hooks, sibling plugins, and `extraKnownMarketplaces` — left intact
  so re-enabling is one line). **Aborts without writing** on malformed/non-object JSON — unlike
  `migrate_plugin.transform_settings`, which resets to `{}` in a migration context where that's
  acceptable; toggling a setting in a file that holds the user's permissions + install reference is
  not. Aligns with the learnings rule that the gentle `enabledPlugins:false` lever is preferred over
  the cascading `marketplace remove`.
- `bin/prawduct-hook` — `cmd_repo_disable` (dry-run default · `--apply` · `--local` · `--json`) +
  dispatch + usage; the applied output carries the take-effect-on-`/reload-plugins` caveat and the
  manual re-enable steps so a direct CLI caller isn't stranded either.
- `skills/repo-disable/SKILL.md` (NEW) — manual-only (`disable-model-invocation: true`),
  `allowed-tools` scoped to `Bash(prawduct-hook repo-disable *), Read`; frames committed-vs-local
  scope (with an onboarded-repo caution) and relays the re-enable path.
- `tests/test_repo_disable.py` (NEW): 13 tests — merge preservation (incl. sibling plugins +
  marketplace), idempotency, never-clobber (malformed/non-object abort), scope routing, and the CLI
  contract that the applied output carries the re-enable guidance.
- `README.md`: new "Turn Prawduct off in a specific repo" section.

**Validation:** full suite 849 passing (+14: 13 new + the auto-parametrized skill-frontmatter
manifest check picking up the new skill). End-to-end against scratch repos — dry-run plan, committed
apply preserving an existing `permissions` block + sibling plugin, local-scope routing, and
malformed-JSON abort. Per-work Critic (cumulative) 0 blocking / 0 warning / 1 note (release-prep
reminder); independent PR review 0 findings.

**Versioning:** patch bump (2.0.11 → 2.0.12). Additive new skill + subcommand; no change to how
existing repos are governed.

## 2026-06-05: silence SessionStart hooks in non-Prawduct repos (shipped v2.0.11)

<!-- prawduct: type=fix | release=v2.0.11 | status=shipped -->

**Why:** Prawduct installs as a **user-scoped** plugin, so its SessionStart hooks fire in every
repo the user opens — including repos that never onboarded. The design intent was already "be
silent where not onboarded" (`hooks/banner.py` and the Stop hook `cmd_stop` both early-return when
there is no `.prawduct/`), but two SessionStart paths never honored it: `hooks/digest.py` injected
the always-on governance digest unconditionally, and `cmd_clear` printed a
`CRITICAL: create .prawduct/artifacts/project-preferences.md` in any repo with source code (the
prefs check is gated on `_has_product_code`, not on `.prawduct/`). Net effect: opening *any*
code repo surfaced Prawduct governance the user never asked for there. Root cause: the
"silent in non-Prawduct repos" invariant lived in convention, not in one shared gate — the
banner/clear/digest hooks were written at different times and the third entry point (the digest,
plugin chunk 6) silently drifted from it. Same silent-inconsistent-invariant class as BLD-7P3K.

**What shipped (via #67 → develop, then v2.0.11):**
- `hooks/digest.py`: new `in_prawduct_repo()` gate at the top of `main()` — resolves the consuming
  repo via `CLAUDE_PROJECT_DIR` (cwd fallback; read-only `.is_dir()`) and emits nothing without a
  `.prawduct/`. The cwd fallback is deliberate (and Critic-confirmed): the digest only reads, so it
  cannot cause a wrong-repo side effect, unlike `banner.py`'s marker-write which justifies its
  no-fallback rule.
- `bin/prawduct-hook` `cmd_clear`: early `return 0` when no `.prawduct/`, mirroring `cmd_stop`. The
  four now-redundant inner `if prawduct_dir.is_dir():` guards collapse into that one top-of-function
  gate (de-indented to `cmd_stop`'s flat style). Behavior-preserving for Prawduct repos.
- `tests/test_plugin_methodology_digest.py` (`TestDigestRepoGate`) and `tests/test_plugin_runtime.py`
  (`TestPluginClearNonPrawductRepo`): first coverage that the SessionStart hooks are silent AND inert
  (no output, no `.prawduct/` scaffolding, no session markers) in a non-onboarded repo with code.
  `_run_digest` now sets `CLAUDE_PROJECT_DIR` explicitly so the gate is deterministic.

**Scope:** the always-on one-line version banner (`hooks/banner.py`) is intentionally retained as
the update-visibility safety net; `/prawduct:*` skills remain registered everywhere (inert until
invoked). Users wanting Prawduct fully disabled in a repo (commands included) set
`"enabledPlugins": {"prawduct@prawduct": false}` in that repo's `.claude/settings.json`.

**Validation:** end-to-end against scratch repos — `digest.py` and `cmd_clear` emit 0 bytes and
create no `.prawduct/` without the marker, and render the digest/briefing with it. Independent PR
reviewer re-ran both hooks both ways to confirm.

**Versioning:** patch bump (2.0.10 → 2.0.11). Pure read-only gating of existing hooks; product
builds in onboarded repos are governed identically.

**Tests:** 835 passing (+4). Cumulative Critic 0 blocking / 0 warning / 0 note; independent PR
review 0 blocking / 0 warning / 1 note (scope clarification — the identity banner stays on; folded
into the PR description).

## 2026-06-05: discovery-capture nudge — prawduct adapts when discovery is uncaptured (shipped v2.0.10)

<!-- prawduct: chunks=01,02 | type=feature | release=v2.0.10 | status=shipped | scope=discovery-capture-nudge -->

**Why:** A repo onboarded via `/prawduct:onboard` and then worked on **docs-first** (or as an
existing codebase) accrues rich product-definition work while `project-state.yaml` stays
template-default — and prawduct never nudged toward discovery. Root cause: `cmd_clear`'s only
"you haven't done discovery" signal (the unfilled-`project-preferences` CRITICAL) was gated on
`has_code`, so a no-code-yet discovery/architecture phase was silent **by construction**. prawduct
keyed on the wrong signal (*code exists*) instead of the right one (*product-definition work exists,
in any form*). Surfaced by the sibling Scriob repo.

**What shipped (via #66 → develop, then v2.0.10):**
- `bin/prawduct-hook` `cmd_clear`: new **DISCOVERY NOT CAPTURED** session-start nudge — fires when
  `project-state.yaml` is template-default (`classification.domain` AND `product_definition.vision`
  both `null`) AND the repo shows product work (source code, or markdown under `docs/`/`documentation/`),
  routing to `/prawduct:discovery`. Conservative both-null gate → "discovery never ran" alarm, not a
  mid-discovery nag; a freshly-onboarded empty repo stays silent. Extracted a shared `_has_product_code`
  helper (the prefs CRITICAL stays code-gated — preferences are a code-time concern).
- `methodology/discovery.md`: new **"Reconciling an Existing or Docs-First Product"** section — read
  existing docs/code → backfill the source of truth → reference `docs/`, don't duplicate.
- `skills/onboard|discovery|doctor/SKILL.md`: onboard routes to `/prawduct:discovery`; discovery names
  the reconcile entry; doctor Health Check #6 (discovery captured).
- `.prawduct/cross-cutting-concerns.md`: new "Discovery capture" pipeline row.
- `tests/test_discovery_capture_nudge.py` (NEW): 19 tests — first coverage for this `cmd_clear`
  detection family; `TestTemplateContract` pins the shipped `templates/project-state.yaml` → detector
  contract so a sentinel reformat fails loud (guards the BLD-7P3K silent-degradation class).

**Validation:** end-to-end against a real `init-product` scaffold and live Scriob (whose parallel
reconciliation flipped the detector uncaptured→silent mid-build). Covered: docs-first,
`documentation/`-first, brownfield-code, fresh-onboard-silent, captured-silent.

**Versioning:** patch bump (2.0.9 → 2.0.10). New always-on detection + methodology; product builds
governed identically — consumers with an uncaptured-discovery repo now get nudged.

**Tests:** 832 passing. Per-chunk Critic 0 findings; cumulative Critic 0 blocking / 0 warning
(1 NOTE → BLD-2R9X filed); independent PR review 0 findings.

## 2026-06-04: CRT-7M2D — cumulative-Critic gate judges commit-coverage, not mtime-recency (shipped v2.0.9)

<!-- prawduct: type=fix | release=v2.0.9 | status=shipped -->

**Why:** The `/prawduct:pr` cumulative-Critic gate (`check-cumulative-critic`) judged the findings
record by mtime vs `.session-start`. That both (a) FALSE-PASSED a stale record over real code
changes (mtime fresh, but `commit_reviewed != HEAD`), and (b) forced a full ~4-10 min cumulative
re-run after every inert post-review fix — the "treadmill" that bit the v2.0.7 and v2.0.8 releases.

**What shipped (via #65 → develop, then v2.0.9):**
- `bin/prawduct-hook` `cmd_check_cumulative_critic`: replaced the mtime/`.session-start` freshness
  block with a **commit-coverage** check — the gate passes iff the record is clean, schema-valid,
  cumulative-mode, and covers HEAD (`commit_reviewed == HEAD`, or the only files changed since are
  docs `.md`). A code change since the review fails (re-run genuinely needed); a doc-only change does
  not. Fails closed on any git error. The `.md`-only carveout reuses the framework's existing
  doc-only definition (no new trust boundary).
- `tests/test_cumulative_gate.py` (NEW): the gate had **zero** direct coverage. 8 real-git tests —
  covers-head, doc-only-delta-covered, code-delta-stale, blocking, missing/unresolved
  `commit_reviewed`, wrong-mode, missing-file.
- Doc sweep: `skills/critic/review-cycle.md`, `skills/pr/SKILL.md`, `methodology/building.md`
  repointed from "fresh" to "HEAD-covering" gate wording.

**Dogfood:** this fix's OWN PR had doc-only post-review fixes, and the gate stayed satisfied without
a cumulative re-run — the treadmill is gone, demonstrated on the very PR that fixes it.

**Versioning:** patch bump (2.0.8 → 2.0.9). Internal governance-tooling correctness fix; no
behavioral change for product builds beyond the (now-honest) PR gate. Closes CRT-7M2D.

**Tests:** 812 passing (+8). Cumulative Critic 0 blocking; independent PR review 0 blocking.

## 2026-06-04: onboard — split repo onboarding out of /prawduct:doctor into /prawduct:onboard (shipped v2.0.8)

<!-- prawduct: type=feature | release=v2.0.8 | status=shipped -->

**Why:** `doctor` connotes health-check (brew/flutter doctor), not setup — so presenting it as the
install/onboard entry point was confusing (owner-raised). The `doctor` skill was also overloaded
with five flows; onboarding was the only one its name didn't fit.

**What shipped (via #64 → develop, then v2.0.8):**
- New **`/prawduct:onboard`** (`skills/onboard/SKILL.md`) — the onboarding entry point: scaffold a
  new *or* existing repo (`prawduct-hook init-product`), or route a pre-2.0 file-sync repo to
  `/prawduct:migrate`. Framed so new and existing repos are the same command.
- **`/prawduct:doctor`** narrowed to health-check / repair / enable-gate / verify / audit-learnings
  — drops the Onboard flow and the `init-product` tool grant; a stray path arg redirects to onboard.
- Onboarding references repointed in `CLAUDE.md`, `README.md`, and the `bin/prawduct-hook`
  `cmd_init_product` docstring (health-check references correctly stay `doctor`).
- **README Quick Start trimmed** to two tight steps — install once at the user level; onboard any
  repo (new or existing) with the same command. The `--add-dir` dev tip moved to "Develop the
  framework itself".
- Tests: repoint the init-product guard to the onboard skill, add a doctor-does-not-onboard guard
  (asserts the tool grant is gone, not just the word), add `onboard` to the bare-command regex.

**Versioning:** patch bump (2.0.7 → 2.0.8). A skill split + doc clarity change; conservative patch
per repo practice. The bump is the marketplace update-cache key.

**Tests:** 804 passing (1 skipped). Cumulative Critic clean (0 blocking; the routing NOTEs +
docstring WARNING resolved in follow-ups); independent PR review clean (0 blocking). Deliberately
did NOT add `/prawduct:onboard` to the session-digest skill list — it's a pre-governance setup
entry, and the digest only fires in already-onboarded sessions (recorded rationale, not an oversight).

## 2026-06-04: rigor-and-stance — sharpen the methodology's PM seams (requirements rigor + agent stance) (shipped v2.0.7)

<!-- prawduct: chunks=01,02,03 | release=v2.0.7 | status=shipped | scope=rigor-and-stance -->

**Why:** Owner-directed pivot from infrastructure to product-management methodology — the infra
foundation was judged stable (v2.0.6 shipped, suite green, develop≡main, backlog ~97% governance
machinery). Sharpen two PM seams the infra-heavy backlog had starved: proportional requirements
rigor, and an explicit agent stance. Design validated by two web-research passes this session
(Claude Code capabilities + agent-design best practices), not first principles.

**What merged (3 chunks, via #63 → develop):**
- **Chunk 01 (requirements rigor):** new canonical `methodology/discovery.md` "Calibrate Rigor to
  Stakes, Knowledge, and Volatility" — rigor scales to stakes × knowledge-confidence × volatility,
  with two distinct research axes (knowledge gap → reason/decompose; volatility/recency → web
  research, with Zig / Claude Code / current-versions examples + a proportionality guard) and
  intentional inference (record each inferred answer as a vetoable
  `[ASSUMPTION: … | impact | correct/override/defer]`). Condensed pointers in `building.md`
  (Before-You-Build + a Decision-Research volatility trigger), the Assumptions element in
  `planning.md` + `templates/build-plan.md`, and a `CLAUDE.md` alignment. building.md token budget
  4650→4720.
- **Chunk 02 (agent stance):** new `methodology/agent-stance.md` — 9 positive, testable stance
  directives (the owner's 6 + verify-own-work, scope-discipline, calibrated-uncertainty), each
  cross-linked to the principle it operationalizes; honesty stances anchored to Anthropic's honesty
  taxonomy. Condensed into the always-on `session-digest.md` (the composable carrier — a
  `force-for-plugin` output style would clobber a consumer's own style, verified). Indexed in the
  methodology skill; cross-linked from `docs/principles.md`.
- **Chunk 03 (digest sweep):** audited artifacts for digest-worthy content; conservative outcome
  (honoring the v1.8.0 anti-bloat diet) — added only the requirements-rigor headline to the digest
  (owner-ratified) and resisted further additions.

**Governance:** per-chunk Critic clean (0 blocking); cumulative Critic 0 blocking / 2 warning / 1
note, all cross-chunk coherence fixes applied (cross-cutting-concerns rows updated/added; filed
STN-6K3D). Full suite green (+5 tests: 798→803). Two durable learnings captured (research-trigger
self-exemption / volatility-vs-knowledge split; canonical-mechanism-vs-structural-constraint).

**Status:** SHIPPED in v2.0.7 (develop→main, 2026-06-04, #63). `regen-views` flipped the build
plan's `## Status` checkboxes to `[x]` and added the v2.0.7 release-notes section + scope rollup.

## 2026-06-04: release-tooling — fix the release/build tooling once and for all (REL-4T8N + 3) (shipped v2.0.6)

<!-- prawduct: chunks=01,02,03,04,05 | release=v2.0.6 | status=shipped | scope=release-tooling -->

**Why:** The v2.0.5 release concretely confirmed REL-4T8N: the per-scope `regen-views` (point the
`active_build_plan` pointer at each of four plans in turn) was 4× tedious, and it surfaced a second
symptom — the derived `release-notes.md` mis-aggregated all scopes of a release under one entry.
Bundled with three adjacent release/build-tooling fixes that cohere in one PR. Designed by a 5-agent
read-only investigation workflow; built sequentially (shared files); one cumulative Critic + a
3-agent adversarial-verification workflow gated the bundle.

**What merged (5 chunks, → develop, release-pending):**
- **Chunk 01 (REL-4T8N-A):** `regen-views` regenerates EVERY release-pending plan in one pass —
  enumerates each change-log `scope=` (status ∈ {shipped, merged}), resolves it to its build-plan
  file via frontmatter `scope:` (`build_scope_to_plan_map`), regenerates each plan's `## Status`
  (per-plan scope re-detection → no cross-scope leakage), de-duped by path, with a single-plan
  back-compat fallback. `diagnose_scope_plan_coverage` warns on merged scopes with no plan file +
  duplicate scopes. Also fixes a latent can't-run state (regen-views previously exit 2 here).
- **Chunk 02 (REL-4T8N-B):** `release-notes.md` renders every distinct scope of a release as its own
  `### ` sub-section with its OWN chunks (no cross-scope union); same-scope entries collapse; a
  single sub-release renders flat (byte-compatible). The `## v2.0.5` digest now shows four correct
  scope sub-sections.
- **Chunk 03 (BLD-8F2Q):** `verify-chunk-refs` existence-checks only the pre-`::` path of a
  `path::symbol` token (symbol stays deferred, BLD-5V8F) — kills a Goal-2 false positive.
- **Chunk 04 (PR-7Q3M):** PR merge-flow step 7 branches on `resolve-base` — delete the plan (resolved
  via the pointer, not a hardcoded path) + clear the pointer when the merge IS the release; RETAIN
  both while release-pending under gitflow. Fixes the latent hardcoded-`build-plan.md` path.
- **Chunk 05 (TST-9K4W):** the two structural test collectors prune the `.claude/` worktree subtree,
  so leftover worktree-isolated workflow checkouts no longer fail the suite.

**Status:** SHIPPED in v2.0.6 (develop→main, 2026-06-04). Full suite green (799 passed, +28 net);
cumulative Critic (0 blocking; the release-notes same-scope-duplicate-heading regression it caught
was fixed) and a 3-agent adversarial-verification workflow (REL-4T8N-A/B + BLD-8F2Q verdict: holds,
byte-identity confirmed) both clean. Merged via #62. Closes REL-4T8N, BLD-8F2Q, PR-7Q3M, TST-9K4W.

## 2026-06-04: cleanup-batch — 6 parallel backlog fixes (refactor/perf/test + critic/pr/methodology docs) (shipped v2.0.5)

<!-- prawduct: chunks=01,02,03,04,05,06 | release=v2.0.5 | status=shipped | scope=cleanup-batch -->

**Why:** Six small, file-disjoint backlog items batched into one PR and built IN PARALLEL via
worktree-isolated workflow subagents (one chunk each), then integrated, full-suite-verified, and
cumulative-Critic'd in the launching session.

**What merged (6 chunks, via #61 → develop):**
- **Chunk 01 (SYN-9C4T):** extract `lib/core.read_bool_yaml_key`; `views.is_views_enabled` delegates;
  the hook keeps a parity-pinned inline mirror (import-light hot path, `prawduct/duplication` waiver).
  Behavior byte-for-byte preserved.
- **Chunk 02 (TST-5W1J):** cache test-file reads in `bin/test-reference-verify` (O(N·T)→O(T)); behavior-preserving.
- **Chunk 03 (BLD-7P3K):** guard test that the active plan's `## Status` chunk IDs resolve to parseable
  `### Chunk <id>:` headings (live guard + good/`####`/missing-colon fixtures).
- **Chunk 04 (CRT-4W8M):** Critic check — exact-match assertions for "no behavior change" refactors → WARNING.
- **Chunk 05 (PRR-4M9T):** trim PR-reviewer goals 7→4 (release-specific); test-evidence-freshness folded
  into Merge Hygiene, not dropped.
- **Chunk 06 (MET-7H2D):** `methodology/building.md` multi-hop edge-case testing guidance (token budget 4560→4650).
Also filed BLD-8F2Q (chunk-ref `path::symbol` false positive) and TST-9K4W (structural tests scan leftover
worktrees), and captured the parallel worktree-workflow build pattern as a learning.

**Status:** SHIPPED in v2.0.5. Full suite green (771 passed, +17); cumulative Critic (0 blocking /
2 warnings resolved / 2 notes) and independent PR review (0 blocking / 0 warning / 1 note) both clean.
The 4th of four scopes shipping together in v2.0.5 (with roi-batch, roi-batch-2, evidence-deferral).

## 2026-06-04: evidence-deferral — test-evidence writer + stop-gate-vs-background-work floor (shipped v2.0.5)

<!-- prawduct: chunks=01,02 | release=v2.0.5 | status=shipped | scope=evidence-deferral -->

**Why:** Two bug reports filed by a downstream product repo (Hallucinote, via `incoming-bugs/`)
and confirmed firsthand. Built directly in the main session (not a workflow — both chunks share
`bin/prawduct-hook` and chunk 02 is design-informed).

**What merged (2 chunks, via #60 → develop):**
- **Chunk 01 (TST-6V2N):** new `prawduct-hook test-evidence record [-- <pytest args>]` subcommand —
  the missing WRITER for the `.prawduct/.test-evidence.json` the `test-status` freshness gate and
  cumulative-Critic staleness check READ. Runs pytest with a JUnit XML report (exact counts),
  stamps `git_sha=HEAD` + ISO timestamp, overlays the F4a coverage half via
  `test-reference-verify --merge-into`, writes atomically. Exit mirrors the suite; evidence written
  either way. Closes the "stamp a fresh sha over stale counts" hole. 5 tests; dogfooded itself.
- **Chunk 02 (STH-3W7F):** doc-only floor + design. `methodology/building.md` Gate-waivers now
  states "in-flight background work is not a waiver case — wait, don't waive" (waiving would skip
  the Critic the completed work still needs). The real fix (a self-declared `.gates-deferred` that
  defers once then re-arms) is recorded in the backlog and DEFERRED — the Stop hook can't detect
  in-flight work itself. building.md token budget 4450→4560 (addition halved first; rationale in-test).
  Also gitignored the `incoming-bugs/` drop-box.

**Status:** RELEASE-PENDING (`status=merged`). This is the THIRD release-pending plan (after
`roi-batch`, `roi-batch-2`); the `develop→main` release runs `regen-views` once per scope. Full
suite green (754 passed, +5); cumulative Critic (0 blocking / 0 warning / 4 notes — 1 WARNING for a
stale plan ref caught + resolved) and independent PR review (0 blocking / 0 warning / 3 cosmetic
notes) both clean. TST-6V2N archived; STH-3W7F stays open (only floor+design shipped; the
`.gates-deferred` code fix is pending).

## 2026-06-04: roi-batch-2 — 9 ROI backlog fixes (views/hook/advisory hardening + tests) (shipped v2.0.5)

<!-- prawduct: chunks=01,02,03,04,05,06,07,08,09 | release=v2.0.5 | status=shipped | scope=roi-batch-2 -->

**Why:** A second round of high-ROI backlog fixes — the 2026-06-04 rough-edges hunt (8 items
verified real before filing, 0 false positives) plus one older re-verified item (TST-1D5W).
Two silent-degradation correctness bugs, a release-process typo guard, parser/gate hardening,
a behavior-preserving constant extraction, and pure test coverage. Built by ONE workflow across
three file-disjoint lanes (HOOK A→B sequential on `bin/prawduct-hook`, ADV + MIG concurrent) and
governed by the launching session (full suite → cumulative Critic → independent PR review).

**What merged (9 chunks/items, via #59 → develop):**
- **Chunk 01 (VWS-3K7P):** `validate_status_values()` warns on change-log `status=` typos in
  `regen-views` (non-fatal stderr); `lib/views.py` docstring reconciled to `{shipped, merged}`.
- **Chunk 02 (STH-2J9F):** `cmd_regen_views` returns exit 1 (not 0) on ImportError — a
  state-mutating command must not report success on a broken install.
- **Chunk 03 (VWS-8M2Q):** drop unsafe chunk IDs from `scope_rollups` YAML (`CHUNK_ID_SAFE_RE`);
  document `_parse_build_plan_frontmatter_scope` unclosed-comment leniency + malformed-frontmatter test.
- **Chunk 04 (STH-6B4R):** gate-freshness sites were already identical-precision — documented the
  invariant + tie rule (`findings_mtime == session_start` is NOT fresh) and pinned it with a test.
- **Chunk 05 (STH-1W5N):** extract `_TRIVIAL_PROTECTED_PATHS` frozenset (single source of truth
  for the trivial/doc-only protected-path bounds); behavior-preserving.
- **Chunk 06 (TST-1D5W):** `_validate_evidence_schema` rejects a bool in an int field.
- **Chunk 07 (TST-7Q3D):** `TestPluginStopGateRegressions` — verify-resolutions out-of-scope,
  trivial-fileset-bounds, unknown-waiver-key cases.
- **Chunk 08 (ADV-9K2T):** `read_store` preserves a `.advisories.json.corrupt` sentinel on
  parse/shape failure of an existing store (surfaces corruption vs a silent reset).
- **Chunk 09 (TST-4H8M):** `TestCollapseBlankRuns` unit coverage for migrate `_collapse_blank_runs`.

**Status:** RELEASE-PENDING (`status=merged`). This is the SECOND release-pending plan (after
`roi-batch`); both ship at the next `develop→main` release, which must run `regen-views` once
per scope (the pointer resolves one plan). The build plan's `## Status` checkboxes stay `[ ]`
until then. Full suite green (749 passed, +35); cumulative Critic (0 blocking / 0 warning /
2 notes — a build-plan heading-depth WARNING was caught and resolved) and independent PR review
(0 blocking / 0 warning / 1 note) both clean. Filed BLD-7P3K (guard test so heading drift fails loud).

## 2026-06-04: roi-batch — 9 ROI backlog fixes (CRT/BLD/TST/MIG + docs) (shipped v2.0.5)

<!-- prawduct: chunks=01,02,03,04,05 | release=v2.0.5 | status=shipped | scope=roi-batch -->

**Why:** Nine pre-triaged backlog ROI items — two reproducible correctness bugs, two
test/cosmetic fixes, and a docs-coherence batch — small and independent enough to build in
one batch. Built by two parallel background workflows (file-disjoint lanes) and governed by
the launching session (full suite → cumulative Critic → independent PR review).

**What merged (5 chunks, 9 backlog items, via #58 → develop):**
- **Chunk 01 (CRT-3M8Q):** critic-mode inference honors the active build plan's current-chunk
  `**Critic mode:**` field as a successive override (`plan-override: <mode>`), routing around
  the Skill-tool `$ARGUMENTS`-not-threading gap.
- **Chunk 02 (BLD-4Q9X):** `scope: null`/empty in build-plan frontmatter suppresses change-log
  scope inference instead of inheriting a stale `scope=` tag — `_parse_build_plan_frontmatter_scope`
  returns `(present, value)`.
- **Chunk 03 (TST-2R7H):** regression truth-table pinning that only `Type: designer-handoff`
  skips the stop-hook Critic gate (new `tests/test_critic_gate_fallthrough.py`).
- **Chunk 04 (MIG-8C3V):** migrate's CLAUDE.md transform collapses 3+ newline runs, dropping
  the leading double blank line.
- **Chunk 05 (docs):** methodology/planning.md (forward-ref convention, step-0 Done-when
  wording, Visual Change Verification section, 8-surface-cascade → token-budget guidance) +
  two design docs repointed from retired `tools/` paths to plugin-native.

**Status:** RELEASE-PENDING (`status=merged`). The build plan's `## Status` checkboxes stay
`[ ]` until the next `develop→main` release flips this entry to `status=shipped` and runs
`regen-views` (per `docs/release-process.md`). Full suite green (714 passed); cumulative Critic
and independent PR review both clean (0 blocking).

## 2026-06-04: v2.0.4 — Intentional-waiver pragma (`prawduct:allow`) + trivial-gate fix (shipped)

<!-- prawduct: type=feature | release=v2.0.4 | status=shipped -->

**Why:** The single-purpose `prawduct:ok-broad-except` marker needed generalizing into one durable, language-agnostic way to declare intentional principle violations; and a 2.0-readiness audit surfaced a real governance hole plus doc/coherence staleness left by the M4 file-sync cutover.

**What shipped:**
- **Waiver pragma `prawduct:allow <scope>/<rule-id> -- reason`** — a general, language-agnostic intentional-waiver mechanism generalizing `prawduct:ok-broad-except` (now `prawduct/broad-except`; legacy spelling still honored). New `lib/waivers.py` recognizer (scope-matched — no cross-waiving; mandatory reason; fail-safe), `docs/waivers.md` spec, canary wiring with a new reason-less-waiver finding, all 49 in-repo legacy usages migrated. `project/*` waivers are opaque to the framework, so a prawduct update can never break a consumer's waivers.
- **Trivial/doc-only gate fix** — `_classify_trivial_change` bounded the deleted `agents/` path and was missing `skills/`, so a `Type: trivial` chunk could have edited the Critic's own protocol (`skills/critic/SKILL.md`) without tripping the catastrophic-blast-radius guard. Fixed test-first (12 new tests the bound never had); reason `agent-file-edited` → `skill-file-edited`.
- **Coherence + ship-blockers** — restored the `GITIGNORE_ENTRIES`↔`_SESSION_GITIGNORED_PATHS` parity test (deleted in M4); fixed dangling refs (`operator_verification.py`, `skills/backlog/SKILL.md`); README/CLAUDE.md/pyproject staleness; backlog hygiene (Open 60→44, 16 archived).

**Versioning:** patch bump (2.0.3 → 2.0.4). Additive + internal-correctness — the legacy pragma spelling is honored and the gate fix only tightens the framework's self-hosting guard, so zero behavioral change for plugin-governed consumers. The bump is the marketplace update-cache key.

## 2026-06-03: v2.0.3 — Retire the file-sync engine & strip pre-2.0 back-compat cruft (M4) (shipped)

<!-- prawduct: type=refactor | release=v2.0.3 | status=shipped -->

**Why:** v2.0.0 cut the framework over to plugin distribution but deliberately kept the v1 file-sync engine frozen as a sibling service for un-migrated repos (`[MIG-M4-REMOVE]`, blocked on a consumer census). Owner directive (2026-06-03): *"we DO NOT need backwards compatibility … remove ANY cruft that exists only for back compat to pre-2.0."* That unblocks M4 — the terminal step of the transition. Governance ships entirely from the plugin; the engine, its payload, and the in-plugin guards that existed only to coexist with it are dead weight.

**What shipped (5 chunks, off `develop`):**
- **Chunk 1 (DOC-4B2W):** namespaced the bare command forms in the 6 plugin-only prose files (`methodology/{building,planning,reflection}.md`, `skills/critic/{review-cycle,review-protocol}.md`, `skills/pr/review-protocol.md`) → `/prawduct:*`; added `TestPluginDocsNamespacing`.
- **Chunk 2:** deleted the file-sync engine — `tools/` (product-hook, prawduct-setup.py, the 3 shims, `tools/lib/`) + 10 pure-engine test files + the lib-parity machinery; repointed the 11 engine-coupled governance-module tests onto the plugin (`lib/` + `bin/prawduct-hook`); relocated `tools/test-reference-verify` → `bin/`.
- **Chunk 3:** stripped the in-plugin pre-2.0 guards — the `_legacy_filesync_present` migrate nudge, the `fallback-no-tools-lib` path, pre-v1.4 verifier-less evidence acceptance, the `legacy_backlog_format_probe`, the coexistence-nudge tests, and three inert sync-stub briefing params.
- **Chunk 4:** removed the 13 file-sync-only templates (7 `skill-*.md` + `product-claude`/`critic-review`/`pr-review`/`build-governance`/`product-settings.json`/`conftest.py`); slimmed `lib/core.py` to the governance helpers the surviving modules use (reshaped `MANAGED_FILES` → a frozenset path registry migrate derives its REMOVE set from); reconciled 7 test files by retargeting content tests to their live plugin source-of-truth or deleting redundant file-sync mirrors (every contract preserved by name).
- **Chunk 5:** removed the committed `.prawduct/{critic-review,pr-review,build-governance}.md`, the sync-manifest gitignore entries, and the dead F5a `.sync-pending` briefing block; swept stale engine refs out of kept code/docs (`bin/prawduct-hook` comment paths + user-facing gate messages, `lib/{views,critic_mode,audit_learnings_cmd}` docstrings/generated strings, README, `docs/project-structure.md`, `cross-cutting-concerns.md`, `project-preferences.md`, the templates' taught commands, the scenario fixtures). Reconciled `[MIG-M4-REMOVE]` and `[DOC-4B2W]`; filed `[JAN-4F7M]` (the janitor skill's Template Currency theme still teaches the file-sync sync-manifest workflow).

**Versioning:** patch bump (2.0.2 → 2.0.3). M4 is internal cleanup — the terminal tail of the v2.0.0 plugin transition — with zero behavioral change for plugin-governed consumers (the engine they don't use is gone). Conservative patch over a minor to avoid version inflation. The bump is the marketplace update-cache key.

**Tests:** 645 passing (down from the pre-M4 ~1810 — the ~1200 deleted were the frozen engine's own suite; net plugin coverage is intact, every retired template-mirror test either retargeted to the plugin source-of-truth or proven redundant with an existing plugin-source test; the cumulative-Critic pass added a 23-principle pin against `docs/principles.md` + a `product-hook` binary-name guard).

**Pre-promotion follow-up (2026-06-04):** the develop→main release-readiness review surfaced one straggler from the M4 retirement — the deferred `[JAN-4F7M]` — so it was folded into v2.0.3 rather than shipped incoherent. `skills/janitor/SKILL.md`'s Template Currency theme (plus its Step 1 framework-health pre-check and Step 7 hash-update guidance) was repointed from the retired `sync-manifest.json`/`framework_source`/place-once mechanism to the read-only plugin templates at `${CLAUDE_PLUGIN_ROOT}/templates/`. The same pass cleaned the two file-sync-era `_METADATA_PREFIXES` entries (`.claude/skills/`, `tools/product-hook`) from both mirrors (`bin/prawduct-hook` + `lib/critic_mode.py`) — a product's own `.claude/skills/` skill now counts as gated code, not excused metadata (closes a small governance hole). Plus the folded comment-only fix to `tests/test_plugin_runtime.py` (stale stop-gate assertion rationale). +7 regression tests (`TestJanitorSkillPluginEra`, `TestMetadataPathClassification`); **652 passing**.

## 2026-06-03: v2.0.2 — Advisory probes run again in the plugin runtime; migration guide leads with the steps (shipped)

<!-- prawduct: type=fix | release=v2.0.2 | status=shipped -->

**Why:** A user migrated a repo onto the plugin and was surprised their backlog wasn't upgraded. Root cause: the `legacy-backlog-format` advisory — the designed nudge toward `/prawduct:backlog migrate` — never fired in *any* v2 plugin repo. Advisory probe evaluation was coupled to the file-sync `sync` step; Chunk 5 excised sync from the plugin runtime and silently took the probe step with it, so `.advisories.json` was read at session start but never populated. The whole advisory channel was dead in plugin repos.

**What shipped:**
- `cmd_clear` (plugin SessionStart) now calls `run_sync_advisories` directly — purely local, fail-soft, full reconcile+persist — before the briefing reads the store, re-homing the orphaned probe step (mirrors the v1 sync-time call). Restores the legacy-backlog nudge and every other advisory probe for plugin repos.
- Two regression tests (fires + persists on a legacy backlog; suppressed once `backlog_format_version: 2`); corrected two stale comments that claimed the hook cannot import `lib`.
- `documentation/MIGRATION.md` restructured to lead with the two-step action and the real install commands (`claude plugin marketplace add` / `install`); background relocated to the bottom.
- Durable learning captured (excising a subsystem silently kills the incidental work it hosted). Filed `[ADV-3K7Q]`: the advisory output still shows un-namespaced skill names (`/backlog migrate`), constrained by the `backlog_probes` byte-parity lock — belongs with the Chunk-13 namespace sweep.

**Versioning:** patch bump (2.0.1 → 2.0.2). Bugfix + doc improvement; the bump is the marketplace update-cache key (an unbumped `main` push does not ship).

**Tests:** 1808 passing.

## 2026-06-02: v2.0.1 — Default to no commit/PR attribution trailers (shipped)

<!-- prawduct: type=feature | release=v2.0.1 | status=shipped -->

**Why:** Prawduct had no attribution guidance at all — the `Co-Authored-By` trailer came purely from the Claude Code harness default. This establishes the prawduct default of NO attribution trailers (`Co-Authored-By` / `Signed-off-by` / "Generated with …"), opt-in per repo.

**What shipped:**
- Default carried by the always-injected session digest (`methodology/session-digest.md`) — the sole surface an already-onboarded repo re-reads, so it reaches migrated repos (thin-anchor CLAUDE.md + place-once `project-preferences.md` that is never regenerated).
- `Commit attribution: none` opt-in toggle in the project-preferences template (set `co-authored` to add the Claude trailer); reinforced in `/prawduct:pr` and this repo's CLAUDE.md.
- New `TestCommitAttributionDefault` contract; durable learning captured.
- Also: `base_branch: develop` set in this repo's `project-state.yaml` so its own gitflow PR/coverage/cumulative-Critic/reviewer gates scope to develop instead of falling back to main (the knob shipped in v2.0.0 Chunk 5 but was never configured on the framework's own repo — surfaced while opening PR #50).

**Versioning:** patch bump (2.0.0 → 2.0.1). The bump is the marketplace update-cache key (an unbumped `main` push does not ship); kept at patch to avoid version inflation for a small additive default.

**Tests:** 1806 passing.

## 2026-06-02: v2.0.0 — Plugin distribution: file-sync → Claude Code plugin (shipped)

<!-- prawduct: chunks=1,2,3,4,5,6,7,8,9,10,11,12,13,14 | release=v2.0.0 | status=shipped | scope=v2.0.0 -->

**Why:** Committing framework files into every consuming repo caused perpetual stash/pop/merge papercuts, silently-drifting governance files, and no clean version signal. v2.0.0 moves distribution from file-sync to a **Claude Code plugin**: consuming repos commit zero framework files (only a small install reference), get always-latest governance via the marketplace, and never fold framework drift into their own commits — while existing file-sync repos keep working until they explicitly migrate.

**What shipped (Chunks 1–14):**
- Installable plugin — `.claude-plugin/plugin.json`, `hooks/hooks.json` (SessionStart banner + briefing + guidance digest; Stop Critic + reflection gates), `bin/prawduct-hook` + `lib/` runtime reading/writing only `${CLAUDE_PROJECT_DIR}/.prawduct/`.
- Framework skills → `/prawduct:*` (critic, pr, janitor, learnings, backlog, advisory, doctor, migrate, methodology + building/discovery/planning/reflection). Critic + PR review protocols bundled as self-contained `context:fork` skills with the read-only-git / no-pytest restriction preserved (CI-pinned).
- Version-delta banner + attributed gates (a block names the version + gate); gitflow release model (`ref: "main"`, `version` as the update cache-key).
- Coexistence — plugin governs, the legacy file-sync hook yields (Chunk 8). `/prawduct:migrate`: one reversible commit cutover, proven byte-airtight on a real consumer (hallucinote, 468/491 files unchanged). Thin static CLAUDE.md anchor.
- Ship-blocker fixed (Chunk 5): gitflow base-branch resolution for the PR/coverage gates + reviewer (honors `base_branch: develop`).
- Dogfood — this repo runs on its own plugin (Chunk 11); real-consumer + parallel-worktree self-containment proofs (Chunk 12).
- Chunk 13 removed file-sync from THIS repo's active path; Chunk 14 relocated the 6 file-sync skill sources out of the load path (byte-identical sync preserved), added **plugin-native new-product scaffolding** (`prawduct-hook init-product` via `/prawduct:doctor`), the consumer `documentation/MIGRATION.md`, `docs/release-process.md`, and swept README/CLAUDE.md/methodology/docs plugin-first.

**Backward compatibility:** existing v1 file-sync product repos are byte-for-byte unaffected — the file-sync engine (`tools/`, the `templates/skill-*` sources, the shims) is frozen and kept as a live sibling service until all local repos migrate (milestone M4, backlog `MIG-M4-REMOVE`). Un-migrated repos `sync` exactly as before.

**Chunk 2 (this release — marketplace published):** `.claude-plugin/marketplace.json` (plugin `source: "./"`) lets a consumer install `prawduct@prawduct` from `github:brookstalley/prawduct@main`. The `autoUpdate` release-surface spike (throwaway public repo, 2026-06-02) confirmed the model empirically: `version` is the update cache-key (a non-bumped `main` push does **not** ship), resolution tracks `main` HEAD (not tags), `develop` is isolated, and the plugin `source` must be `"./"` — a `{ "source": "github", … }` object SSH-fails for HTTPS/`gh`-auth users even on a public repo. First flag-free open prompts once to trust the marketplace. Full results in `docs/release-process.md`.

**Tests:** 1804 passing.

## 2026-06-01: v1.8.1 — Bugfix: phantom "rebase in progress" from stale `.git/REBASE_HEAD` (release)

<!-- prawduct: type=bugfix | release=v1.8.1 | status=shipped -->

**Reported by:** Hallucinote (downstream product repo), 2026-05-30 — "where is this rebase thing coming from? Seems like prawduct is misleading us every single time."

**Symptom:** `_git_op_in_progress()` (`tools/lib/sync_cmd.py`) reported a "rebase in progress" when no rebase existed. This is *persistent governance noise*: it misled every session briefing and could silently suppress a legitimate framework auto-sync (a non-empty return is a hard auto-commit precondition). Because the detected op is cached into `.prawduct/.sync-pending` and the briefing replays that string verbatim each session, the phantom was sticky until manually cleared.

**Root cause:** `REBASE_HEAD` was in the marker-file list, but — unlike `MERGE_HEAD` / `CHERRY_PICK_HEAD` / `REVERT_HEAD`, which git removes when the op ends or aborts — **git leaves `.git/REBASE_HEAD` behind after a rebase completes**, overwriting it only on the next rebase. Its presence is not an in-progress signal. The authoritative test (the `rebase-merge` / `rebase-apply` directory check, which is what `git status` uses) was already present and correct.

**Fix (one line + comment):** removed the `("REBASE_HEAD", "rebase")` marker. Real rebases are still detected via the directory check, so no behavior is lost. Because the auto-commit step recomputes blockers fresh on every sync run and `.sync-pending` is cleared/overwritten each run, the fix is **self-healing** — existing affected repos clear the stale marker on their next sync, no manual intervention. (The report's secondary suggestion — re-evaluating cached blockers at briefing time — is therefore unnecessary for this bug and was left unimplemented per scope discipline; noted as a future robustness candidate.)

**Why tests missed it:** `test_rebase_in_progress_blocks_commit` simulates a rebase with the `rebase-merge` *directory*, so it passed via the correct branch and never exercised the `REBASE_HEAD` *file* branch — the buggy line was effectively untested.

**Test coverage:** 1605 passing (+8). New `TestGitOpInProgress` exercises the corrected function directly (clean repo, stale `REBASE_HEAD` → no op, real `rebase-merge`/`rebase-apply` dirs → rebase, and `MERGE_HEAD`/`CHERRY_PICK_HEAD`/`REVERT_HEAD` still detected), plus `test_stale_rebase_head_does_not_block_commit` proving auto-commit proceeds with a stale ref present. `test_rebase_in_progress_blocks_commit` still passes, confirming real rebases remain blocked.

**Backward compatibility:** Strictly a correctness fix to detection logic; no contract change. Affects every version that ships `_git_op_in_progress`.

## 2026-05-30: v1.8.0 — Governance-tax reduction: pure benefit, almost no tax (release)

<!-- prawduct: chunks=A,B,C,D,E | release=v1.8.0 | status=shipped | scope=v1.8.0 -->

**Why:** A cross-product review (hallucinote, war-castle) plus a 5-channel audit of the framework's own feedback surfaces found the governance *tax* had crept up until the signal was drowning in noise — "so much feedback it's barely worth using." The goal of this release is to restore a **pure-benefit, almost-no-tax** posture: a healthy session opens near-silent, broken tooling works, and every surfaced line is actionable *now*. The fixes are symptoms of one root pattern — the framework over-produces feedback, much of it about itself.

**Release shape:** Five chunks.

- **A — Ship `tools/lib/` to product repos (fix `ModuleNotFoundError`).** `tools/product-hook` imports `from lib import …` (regen-views, operator-verification) but `tools/lib/` was in no sync set, so every synced product repo crashed on those commands — confirmed in hallucinote (blocked across ~6 PRs) and war-castle (vendored `lib` by hand). New `MANAGED_DIRS` + `effective_managed_files(fw_dir)` enumerate `tools/lib/*.py` dynamically (no static list to drift — that footgun *is* the bug). Ships eagerly + idempotently on init/migrate; existing synced repos self-heal via the sync backfill, no per-product migration. The three unguarded import sites degrade gracefully; `validate` flags a missing lib; the project-preferences "has code" heuristic now excludes framework tooling so shipping lib doesn't falsely fire the CRITICAL on a fresh empty repo. 16 regression tests.

- **B — Silence sync on the happy path.** A healthy up-to-date repo now produces *zero* sync/freshness noise. Manifest freshness markers (`last_sync`, `framework_commit`) refresh on every successful sync, not only when a file changed — killing the phantom "N commits behind" an identical repo reported forever. The template-drift advisory fires **once** per template change then self-resolves (was re-nagging every session with no dismiss path — the single largest advisory tax; the user's place-once file is never overwritten). The per-file sync action dump collapsed to a count line. The "auto-sync didn't apply" version NOTE became outcome-aware for free (fires only on genuine sync failure).

- **C — Session briefing diet.** Cut the every-session noise: the `Tests: ~N` line, the "Last Critic review took … grumpier" quip, and the recurring CLAUDE.md-large nag (raised to a genuine-bloat 250-line bar; the soft 150 guideline is already enforced by the Critic at review time). Collapsed three multi-line blocks to one line each: the learnings topic index → count + `/learnings` pointer; the backlog 5-item dump → `Backlog: N pending (/backlog to triage)`; the freshness HEAD/last-sync/commit/version table → a single "Framework drift" line on real drift only. Deduped the three ways framework drift was being reported into one owner per axis. Net: a steady-state briefing of ~5 actionable lines vs the prior ~15-line wall. Removed the orphaned test-count helpers.

- **D — Stop the backlog from re-inflating.** The backlog's real problem was structural: Critic NOTEs on framework internals and cross-product reflections auto-filed into the *pickable* backlog (43% of items were Critic-filed; 10 were Critic-about-Critic — a self-portrait of the tooling reviewing itself). `methodology/reflection.md` + `templates/critic-review.md` now gate filing on a real, near-term consumer — internal ceremony and cross-product lessons get reflected/learned, not filed ("would an owner with 30 free minutes pick this?"). Closed SYN-2K9N (resolved by B's fire-once). The existing 24-item self-nag burn-down is left as an owner-ratifiable recommendation (`documentation/governance-tax-followups.md` §4), not executed unilaterally.

- **E — Restrict the Critic to read-only git (CRT-2M5P) + pytest probe (CRT-8H3D).** The Critic's `allowed-tools` carried broad `Bash(git *)`, which once let a review run `git checkout` mid-review and corrupt the working tree to detached HEAD. All three Critic surfaces (critic, template, critic-test shadow) now grant explicit read-only git verbs only. Added the negative-path probe CRT-8H3D asked for: the structural pytest block is the *pure-allow* list (no allow pattern matches a pytest command); the `!`-deny entries are documented as non-functional. Both items closed.

**Decisions recorded (Principle 4):**
- **Dynamic managed-directory over a static module list (A).** Listing `tools/lib`'s modules statically would silently re-introduce the `ModuleNotFoundError` class every time a module is added. Enumeration keys off the framework dir, which also preserves the static `MANAGED_FILES` set for unit tests that pass an empty fake framework.
- **Template-drift fire-once over a dismiss flow (B).** Place-once files are user-owned ("surface the change once, then it's yours"), so auto-resolving after one surfacing matches the semantics without new dismiss machinery — a cleaner fix than the `dismissed_advisories` list SYN-2K9N proposed.
- **Cut the briefing soft-CLAUDE.md nag, keep a genuine-bloat alarm (C).** The Critic owns the soft 150-line guideline at the actionable moment; the briefing keeps only a 250+ real-problem signal.
- **NOTE diet DESCOPED (E), recorded not dropped (Principle 2).** On scrutiny the candidate NOTEs (backlog-reconciliation, operator-verification, canary check #1) are conditional + actionable *signal*, not every-session tax; cutting them reduces signal. "Pure benefit, almost no tax" means cutting noise, not signal — over-cutting to hit a diet target would itself be a failure.

**Backward compatibility:** Backward-compatible (minor bump). Existing products *gain* `tools/lib/` and the quieter briefing/sync on their next sync — no migration, no breaking change. The Critic git-allow-list narrowing is strictly more restrictive (read-only ⊂ all), and every prior read-only git operation the Critic used is still permitted. Two product-facing contract changes were deliberately *deferred* to `documentation/governance-tax-followups.md` rather than shipped here: the Critic 4-mode→2-mode collapse and the session-start `--no-pull` change (both need an owner decision + migration). The banner is bumped to v1.8.0 in `.claude/settings.json` and `templates/product-settings.json`.

**Test coverage:** 1597 passing (0 failed). Net change reflects ~16 new lib-propagation tests, sync-silence + briefing-diet + critic-safety tests, minus consolidated/removed tests for cut behavior (briefing item-dump, test-count helpers). Every chunk passed an independent `/critic` chunk review (A: 3 warnings resolved; B: clean; C: 1 warning resolved; D: doc-only; E: 1 warning + 2 notes resolved).

**Out of scope (filed as proposals, not pickable work):** Critic mode collapse, artifact-drift auto-detection, session-start sync timeout/`--no-pull`, and the 24-item self-nag burn-down — all in `documentation/governance-tax-followups.md`.

## 2026-05-29: v1.7.0 — Backlog system (Phase 2 lean core): structured `/backlog` skill + first production advisory probe (release)

<!-- prawduct: chunks=01,02,03,04 | release=v1.7.0 | status=shipped | scope=v1.7.0 -->

**Why:** Every Prawduct product accumulates a flat `.prawduct/backlog.md` — bullets appended by builder, critic, reflection, and janitor, with two by-convention sections (`## Active — next up`, `## Queue`), no IDs, no metadata, no grouping. This repo had 44 such items spanning months. The pain (requirements §1): picking next-work meant re-reading the whole file; items didn't group; dedup was manual; stale items didn't surface. The user-facing test: **can someone with 30 free minutes pick a high-value item and ship it, without first spending 15 minutes triaging?** This release is **Phase 2** of the three-phase post-sync-advisory build (infra → backlog → prompts); Phase 1 (v1.6.0) shipped the advisory mechanism with an empty probe roster, and this phase registers the first **production** probe against it — proving the mechanism carries a real signal.

**Release shape:** Four chunks. 01 — format foundation: the structured item shape (`[PFX-XXXX]` id + backticked dot-separated metadata bar + free-form body), the three-section file (`## Open` / `## Promoted` / `## Archive`), the `project-state.yaml` resolution-field stubs, and the forked monolithic `/backlog` skill registered in **both** `SKILL_PLACEMENTS` (new repos) and `MANAGED_FILES` (existing repos via sync) with the foundational `add`/`list`/`find`/`update` subcommands; the fork read/write/prompt path was smoke-validated end-to-end. 02 — `pick` (doc-only): prose→filter interpretation with confirm-back (Q3), the budget/type/area filters, the `impact/effort` recency-weighted ranking with a legacy-item penalty, and Q6 build-plan-aware prioritization (rank items overlapping the `active_build_plan` scope first). 03 — the adopt-the-structure loop: the single `legacy-backlog-format` probe (`tools/lib/backlog_probes.py`, idempotent `register_backlog_probes()`, count-stable evidence) wired into `run_sync_advisories`, plus the `migrate` subcommand that converts legacy items and writes `backlog_format_version: 2` to resolve the probe. 04 — this release (version bump, change-log, spec status, deferred-item filing, dogfood migration + pick, banner bump, cumulative review).

**Architecture decisions (recorded):**
- **Skill-driven CLI, Python probes only (Q5).** The eight `/backlog` subcommands are driven entirely by the forked `SKILL.md` (no Python `backlog_cmd.py` — explicit user choice, diverging from the `/prawduct-advisory` `advisory_cmd.py` precedent). Only the probe is Python, because it registers against the Phase-1 `register_probe` registry and runs inside `run_sync_advisories` where no skill executes. **Consequence (Requirements Confidence: Medium):** the headline behaviors — `pick` ranking, prose→filter parsing, `migrate` inference — live in a prompt and are **not unit-testable**. They are validated by dogfooding (this chunk's migration of the real 44-item backlog) and scenario review, not an automated suite.
- **Two stores, sharply distinct (inherited from v1.6.0 spec §3.5).** The skill *writes* resolution facts (`backlog_format_version: 2`) to the committed, shared `project-state.yaml`; the probe *reads* them. A teammate's committed migration resolves the `legacy-backlog-format` advisory for everyone on next sync. The per-clone `.advisories.json` nag log is never touched by the skill.
- **Explicit registration, no import-time side effects.** Backlog probes live in a plain module that `run_sync_advisories` imports immediately before `run_all_probes` (a "load feature probes" step), preserving Phase 1's deliberate empty-at-import registry.
- **Resolved open questions Q1–Q7** decided with the user this session: starter prefix vocabulary + optional `backlog_prefixes:` (Q1); janitor proposes the archive-split past ~200 entries (Q2); the LLM interprets pick prose natively with a confirm-back ceiling, no programmatic parser (Q3); tags+plaintext find, no semantic search in v1 (Q4); `context: fork` monolithic skill (Q5); **Q6 overrode the requirements' lean** — `pick` *prioritizes* items overlapping the active build plan rather than warning-and-suggesting-standalone; external-backlog detection scans repo root + `.github/` only (Q7).

**Proportionality — lean core shipped, rest deferred (Principle 11).** This release shipped the lean core the §1 user-facing test needs, not the full §6/§7/§8.2 surface. The deferred scope is **filed, not dropped** (Principle 2) — eight structured backlog items under `## Open` ([BKL-2F7K] the three remaining §8.2 probes, [BKL-5H9M] `/backlog import`, [BKL-3R8P] `/backlog dedup`, [JNT-7T1W] janitor Step 2.5 triage incl. the Q2 archive-split, [CRT-3K9P] the four C-B1–C-B4 Critic checks, [BKL-4N6X] the `/backlog dismiss-advisory` alias, [BKL-6L3Q] the build-plan hygiene-step doc, [BKL-1V8J] the prawduct-doctor external-file report). Each is held back because the low-risk profile and absence of a current consumer don't justify the cost/friction yet; add when a real product needs it.

**Dogfood (verification layer 3 / success criterion S4 + S1).** Ran `/backlog migrate` on this repo's real **44-item** legacy backlog: all 44 converted to the structured shape (IDs derived from area, sources read from the trailing parenthetical markers, bodies preserved verbatim — content-preservation verified by snippet diff against the pre-migration file), legacy `## Active`/`## Queue` headings folded into `## Open`, the one `[RESOLVED v1.6.0 Chunk 06]` item moved to `## Archive` with `status: shipped` + `closed-by: v1.6.0 Chunk 06`, and `backlog_format_version: 2` written (which auto-resolves the `legacy-backlog-format` advisory on next sync — confirming the round-trip). Then `/backlog pick something quick and high-impact` returned three ranked candidates with one-line rationale in seconds (S1), after running the build-plan-overlap check. The skill-driven architecture's testability cost is repaid by this end-to-end dogfood: the migration is the integration test the unit suite can't be.

**Backward compatibility:** New feature, backward-compatible (minor bump). Existing products are unaffected until they sync and *choose* to migrate — legacy unstructured items remain valid (tools treat them as `area: untagged`, rank them lower) and nothing forces migration; the `legacy-backlog-format` advisory only *nudges*. The `/backlog` skill registers in both placement maps so existing products receive it on next sync, consistent with the other skills. The companyAnnouncements banner is bumped to v1.7.0 in `.claude/settings.json` and `templates/product-settings.json` (propagates to product repos on sync).

**Test coverage:** 1583 passing (0 failed) — +17 over v1.6.0's 1566, from the Chunk 03 probe suite (`tests/test_backlog_probes.py`: trigger/resolution/idempotency/supersession against synthetic fixtures + a sync→resolve integration test) plus the extended exact-set registration tests (`test_has_all_managed_files`, `test_v4_product_gets_new_skills`, manifest) and template-structure assertions. The skill prose (`pick`/`migrate`/format) is not unit-testable by design — covered by the dogfood above.

**Critic-resolution audit:**
- **Chunk 01:** `final` (architectural-keystone override) — format-contract coherence verified before Chunks 02–04 built on it; fork read/write/prompt path confirmed.
- **Chunk 02:** `chunk`/doc-only — `pick` prompt coverage reviewed (prose parsing, ranking, Q6 overlap logic); no executable code, test-evidence step skipped.
- **Chunk 03:** `chunk` — 0 findings. Probe uses the Phase-1 advisory API correctly; idempotent `register_backlog_probes()` sidesteps the `clear_registry`-wipe trap; resolution via `backlog_format_version` reconciles to `resolved_by: sync`; lazy import in `run_sync_advisories` breaks the circular dependency; the broad-except is pragma-marked at a genuine boundary.
- **Chunk 04 (release):** cumulative `/critic` against `merge-base(main)…HEAD` (`c1184b4…6ec1238`, 22 files) as the `/pr create` gate — **0 BLOCKING, 0 WARNING, 1 NOTE**. The lone NOTE ("`backlog/SKILL.md` omits `disable-model-invocation: false`") was a **verified false positive** — the field is present at frontmatter line 5; a fork-context misread, the pattern already tracked in the backlog. Probe design, two-store separation, learnings-adherence, scope discipline, and the 44/44 dogfood migration all confirmed clean.

**Out of scope (permanently / later phase):** prompt-management probes/feature (Phase 3 — advisory-spec §13, `prompt-management-requirements.md`); semantic/embedding related-item search (Q4); GitHub Issues sync, cross-product aggregation, per-user assignment, `/backlog graph` (requirements §11); a Python `backlog_cmd.py` CLI (user chose skill-driven).

## 2026-05-29: v1.6.0 — Post-sync advisory infrastructure (Phase 1) + configurable build-plan path (release)

<!-- prawduct: chunks=01,02,03,04,05,06,07 | release=v1.6.0 | status=shipped | scope=v1.6.0 -->

**Why:** Two upcoming features — the backlog system (`documentation/backlog-system-requirements.md` §8.1) and prompt management (`documentation/prompt-management-requirements.md` §11.1) — each need to notice "this project should probably do X, but we won't force it" and nudge the user at session start until they act or dismiss. The pattern is general (sync probes detect signals → advisories written to a shared store → next briefing surfaces them → user runs the recommended command or dismisses). Specifying it once as shared infrastructure prevents the two feature build plans from each inventing an incompatible version. `documentation/post-sync-advisory-spec.md` (v0.2) is the design; this release builds its Phase 1.

**Release shape:** Seven chunks. 01 — architectural spine (`tools/lib/advisory_store.py`: `.advisories.json` schema, return-value reader/writer, `AdvisoryCandidate`, the `<feature>-<type>-v<version>-<hash6>` id, `ProjectState`/`Codebase` wrappers, the probe registry, the active/resolved sync diff, the `ADVISORIES (post-sync, N active)` briefing section). 02 — sticky dismissal + undismiss. 03 — probe-version supersession. 04 — retention/compaction/TTL-GC/soft-caps + schema-version read-tolerance. 05 — the `/prawduct-advisory` CLI (`advisory_cmd.py` + `product-hook advisory` dispatch + skill). 06 — configurable active build-plan path (see below), added mid-release when the release chunk's `regen-views` step exposed the hardcoded-`build-plan.md` gap. 07 — this release (version bump, change-log, spec status, no-op integration test, cumulative review).

**No-op infrastructure ship (spec §13).** The production probe roster is **empty** — no probe is registered at import time — so a synced project sees zero new advisories. The mechanism is complete and exercised end-to-end via a synthetic test probe that is never registered in production. The integration test `TestRunSync::test_noop_ship_empty_production_roster` proves a real `run_sync` produces an empty `.advisories.json` and no ADVISORIES briefing section (A1/A2/A5 at the production-roster level). This keeps the first ship trivially rollback-safe and lets each feature's build plan assume the mechanism exists.

**Key semantics recorded (decisions made across chunks):**
- **Two stores, sharply distinct (spec §3.5).** `.advisories.json` (gitignored, per-clone) is the *nag log* — active triggers + per-developer dismissal/resolution. `project-state.yaml` (committed, shared) is the *answer store* — settled facts probes read as resolution conditions. A teammate's committed answer resolves an advisory for everyone on next sync; a dismissal never leaves the per-clone log.
- **Probe-version supersession (Ch 03, spec §2.8/Q1/A8).** When a probe's version bumps, the bumped candidate carries a new id (version is in the hash), so the prior active advisory for the same `(feature, type)` is marked `resolved` / `resolved_by: probe-update` / `superseded_by: <new-id>` rather than plainly resolved; the new advisory is written `active`. The user sees one current advisory per `(feature, type)` tuple.
- **Dismissed-then-version-bumped is NOT superseded (Ch 03).** A dismissed advisory's dismissal is the load-bearing per-clone fact and is kept; the bumped probe's new id is a distinct condition that surfaces as a fresh `active` advisory. Rationale: the user dismissed the *old* probe's finding, so a materially-refined probe gets a new chance to nag.
- **Compact retention form (Ch 04, spec §3.4/Q4).** On each sync, non-active entries shrink to load-bearing fields (resolved → `id`/`state`/`resolved_at`/`resolved_by`[+`superseded_by`]; dismissed → `id`/`state`/`dismissed_at`/`dismissed_reason`). Resolved entries are GC'd after a 30-day TTL (boundary kept; missing/garbled `resolved_at` never deletes). Soft caps 100 active / 50 resolved / 200 dismissed, newest-per-band kept. Retention lives in `run_sync_advisories`, separate from `reconcile` (state-diff vs storage-hygiene). **Consequence:** once a resolved entry is compacted, a later re-trigger reactivates it with a *fresh* `triggered_at` — the original is gone with the compaction; arguably more correct (a re-trigger after a fix is a new occurrence).
- **Schema-version read-tolerance (Ch 04, A7).** A lower/absent/garbage `schema_version` is forward-migrated to current; a higher version (written by a newer prawduct) is read as-is, never crashed on.
- **Action-driven resolution (Ch 05, spec §4.3/Q3).** `/prawduct-advisory resolve` (and a feature action's success path) can mark an advisory resolved immediately with `resolved_by: "action"`, without waiting for the next sync. The authoritative path remains the `project-state.yaml` fact + probe re-run; this is the immediate-feedback shortcut.
- **`show` evidence reconstruction (Ch 05, Q5).** The in-store evidence array stays capped at 5; `/prawduct-advisory show <id>` re-runs the probe to reconstruct the full uncapped citation list for a compacted entry (active entries return their stored array, no scan).
- **undismiss-after-compaction rehydration (Ch 05, Critic-found).** `undismiss` flips a *compacted* dismissed stub to active, but compaction had dropped its load-bearing fields. `reconcile` now rehydrates such a stub (detected by a missing `triggered_at`) from the fresh candidate when the probe still fires, or auto-resolves it when the probe is silent — so an undismissed advisory never renders with a blank summary indefinitely.
- **Configurable active build-plan path (Ch 06).** The build-plan-consuming tooling (`regen-views`, `infer-critic-mode`, the stop-hook Critic/staleness gates, the session-briefing work-context parser, `verify-chunk-refs`, `check-pr-trivial`) hardcoded `.prawduct/artifacts/build-plan.md`, so projects that name their plan by scope (`v1.6.0-advisory-infrastructure-plan.md`) were invisible to it — the recurring Critic NOTE across chunks 02–05, and the reason this release's `regen-views` step initially failed. An optional `active_build_plan:` scalar in `project-state.yaml` now names the active plan (relative to `.prawduct/`); a shared `core.resolve_build_plan_path` returns the pointer target when set and falls back to `artifacts/build-plan.md` when absent — **zero behavior change** for repos that don't set it. The resolver is mirrored inline in the standalone `tools/product-hook` and pinned to the lib copy by a parity test (same discipline as the `GITIGNORE_ENTRIES` mirror). Both standard and scope-named plans are now first-class. This repo sets the pointer to its v1.6.0 plan and dogfoods the resolver via `regen-views`.

**Backward compatibility:** Zero user-visible change. The `.advisories.json` store is new and gitignored; existing repos get an empty one on first sync. The advisory probe step in `run_sync` is wrapped so a faulty future probe can never block a sync, and degrades to a note. The unrelated template-drift `advisories` key in `run_sync`'s return dict (the "Place-once template advisories" briefing line) is untouched and kept distinct. The `/prawduct-advisory` skill is registered in **both** `SKILL_PLACEMENTS` (new repos via init) and `MANAGED_FILES` (existing repos via sync), so existing products receive it on their next sync — consistent with the other five skills.

**Test coverage:** 1566 passing total at v1.6.0 (0 failed). New test classes: the `/prawduct-advisory` CLI suite (`tests/test_advisory_cmd.py` — list filters/A6, show evidence reconstruction/Q5, action resolve, dismiss/undismiss, `TestUndismissAfterCompaction`, and `run` dispatcher flag-parsing/exit-codes), `TestAdvisoryDispatch` (subprocess-level `product-hook advisory` wiring), the no-op-ship integration test (`TestRunSync::test_noop_ship_empty_production_roster`), and the build-plan resolver suite (`tests/test_build_plan_resolution.py` — resolver cases + lib↔product-hook parity) plus pointer cases in `test_views.py`/`test_critic_mode_inference.py`, atop the per-chunk store tests added in 01–04.

**Critic-resolution audit:**
- **Chunk 01:** `final` mode (architectural keystone override) — spine coherence (store ↔ registry ↔ sync-diff ↔ briefing) verified before later chunks built on it.
- **Chunk 02 / 03:** dismissal lifecycle and supersession reviewed; recurring `infer-critic-mode` rule-4 gap (helper keyed to hardcoded `build-plan.md`; this plan is `v1.6.0-advisory-infrastructure-plan.md`) fail-safed to `final` — already backlogged, no new item.
- **Chunk 04:** clean — 0 blocking, 2 defensive-edge notes (no change made); the retention/`reconcile` seam fell exactly on the state-diff / storage-hygiene boundary, so no Ch 01–03 test needed weakening.
- **Chunk 05:** `final` → 0 blocking, 2 WARNING + 2 NOTE. W1 (untested `product-hook advisory` dispatch) closed with subprocess tests; W2 (undismiss-after-compaction degraded advisory — a real correctness bug in a newly-reachable path) closed with the `reconcile` rehydration branch + a dismiss→sync→undismiss→sync test. Design NOTE addressed by extracting the `_mutate_advisory` skeleton behind dismiss/undismiss/resolve. `verify-resolutions` re-review → no new findings.
- **Chunk 06:** `final` → 1 BLOCKING (an unsubstituted test-count placeholder token left in this change-log entry — substituted with the real 1566) + 1 NOTE (mixed Ch06/Ch07 working tree; cumulative review pending). Resolver design confirmed clean: lib↔product-hook duplication pinned by a parity test, every active build-plan reader routed through the resolver, back-compat covered, no-op-ship claim independently verified (`register_probe` appears only in test files).
- **Chunk 07 (release):** cumulative `/critic` against `merge-base...HEAD` as the `/pr create` gate.

**Out of scope (per spec §13/§14):** production probes (Phase 2 backlog probes §8.2, Phase 3 prompt probes §8.1), per-feature dismissal aliases (`/backlog dismiss-advisory`, `/llm-strategy dismiss-advisory` — ship with their owning features), a rich `Codebase` content scanner, team-wide advisory state, time-based auto-dismissal, cross-product aggregation, and stop-hook gating on advisories (advisories are informational, never gates — spec §9).

## 2026-05-23: v1.5.2 — Stop-hook waiver discoverability (release)

<!-- prawduct: chunks=01 | release=v1.5.2 | status=shipped | scope=v1.5.2 -->

**Why:** User-reported infinite-loop pathology in hallucinote on 2026-05-23. Pathology: a build-plan chunk typed `code` (default) but actually in a designer-handoff phase (human-only Max-for-Live `.amxd` authoring) hit the CRITIC REVIEW gate every session end — build plan active + code changes + no fresh Critic findings — with no path to satisfy the gate (Critic legitimately couldn't review without GO/NO-GO). The `.gates-waived` escape hatch existed in build-governance.md but was never named in the blocker text itself; agents without prior knowledge of it edited/retried repeatedly, burning tokens. User flagged it as "a major prawduct bug if an error in build plans can cause an infinite token-eating loop for agents."

**Release shape:** One chunk — surface `.gates-waived` in four stop-hook blocker stderr messages (REFLECTION, CRITIC REVIEW default, CRITIC REVIEW verify-resolutions-stale, PR REVIEW). Each blocker now appends a tight "Escape hatch:" snippet naming the file path, the per-gate JSON shape (`{"reflection"|"critic"|"pr": "reason"}`), the trigger condition (e.g., "chunk is in a designer-handoff phase, blocked by an external dependency, or the GO/NO-GO is not yet verifiable"), and a back-link to `build-governance.md` "Gate Waivers". The CRITIC REVIEW default blocker additionally names the *structural* alternative (`Type: designer-handoff` in the build plan) for chunks where Critic is fundamentally unsatisfiable by design — that's the permanent fix; the waiver is the session-scoped escape.

**Backward compatibility:** Zero behavior change. All gates fire on the same triggers and clear on the same conditions as v1.5.1. The waiver mechanism, the JSON schema, and the auto-clear-at-session-start lifecycle are unchanged — this release surfaces what was already implemented. No template or skill changes — purely a stop-hook stderr-text addition.

**Test coverage:** 1444 passing (1440 → 1444). New regression test class `TestBlockerMessagesNameWaiverEscapeHatch` with 4 tests pinning `.gates-waived`, the per-blocker waiver-key (`"reflection"` / `"critic"` / `"pr"`), and the `build-governance.md` back-link in each blocker's stderr. The verify-resolutions-stale test also pins the parenthetical "(verify-resolutions stale)" distinguishing it from the default CRITIC variant. Suite duration 156.65s; no other tests touched.

**Critic-resolution audit:**
- **Chunk 01:** chunk-mode → 1 BLOCKING (build-plan ref drift — `## Chunk 01:` (h2) breaks `verify-chunk-refs` which requires `### Chunk NN:` (h3); also `_parse_build_plan_chunk_type` would silently fall through to `code` default) + 1 NOTE (PR REVIEW blocker added during build but not named in the plan — scope expansion). BLOCKING fixed by promoting both build-plan files' chunk heading to h3 and removing a backticked `.prawduct/.gates-waived` ref the verifier mistook for a code-deliverable. NOTE resolved by updating both plan files to name all 4 blockers in Description / Deliverables / Done-when / Acceptance Criteria with the explicit rationale. verify-resolutions re-review → 0/0/0 clean.

**Out of scope (deferred to future release):** A *structural* loop-detection counter that escalates after N re-fires of the same blocker with no progress. Discoverability is the high-ROI piece — once the agent reads "you can declare a waiver if this gate cannot be satisfied this session," the loop ends. The counter is defense in depth for agents that still ignore the escape hatch; needs design pass on per-fire signature, threshold, and escalate-vs-downgrade choice. Filed in backlog "Active — next up" alongside the original pathology entry.

**Backlog items closed:** "Stop-hook blockers do not surface the `.gates-waived` escape hatch — agents can infinite-loop on a mis-typed chunk" (2026-05-23, partial — discoverability fix shipped; loop-detection counter deferred).

## 2026-05-23: v1.5.1 — Backlog follow-ups (release)

<!-- prawduct: chunks=01,02,03,04,05 | release=v1.5.1 | status=shipped | scope=v1.5.1 -->

**Why:** v1.5.1 is a maintenance bundle of five highest-ROI backlog items captured during v1.4/v1.5 — one active bug (`regen-views` flipping the wrong checkboxes via cross-version chunk-ID collisions), one recurring violation (Critic invoking pytest despite the prose rule), one defense-in-depth gap (`_compute_verify_resolutions_scope` reachable only via SKILL prose), and three surgical follow-ups (chunk-Type parse-error surfacing, classifier metadata symmetry, gitignore-test brittleness). Treating them as one release amortizes the per-chunk Critic-pass overhead and clears the highest-friction items in one PR.

**Release shape:** Five chunks across the standard cadence — Chunk 01 (`regen-views` scope-aware Status flipping), 02 (Critic `allowed-tools` deny-list — block pytest invocation), 03 (expose `compute-verify-resolutions-scope` as CLI subcommand), 04 (three bundled follow-ups: parse-error surfacing, classifier metadata symmetry, gitignore-test hardening), 05 (this entry — version bump, change-log, regen-views dogfood, PR creation).

**Backward compatibility:** Zero regression risk for products that don't opt into the new scope tagging — Chunk 01's `_detect_active_scope` returns None and `collect_shipped_chunks` falls through to the legacy unfiltered union. The new `compute-verify-resolutions-scope` subcommand is additive; the Critic SKILL surfaces have been updated to call it but legacy product repos without the helper get the existing prose fallback. The Critic `allowed-tools` deny patterns are additive in skill frontmatter (preserves existing legitimate Bash allowances). Chunk 04 changes are surface-level fixes — the trivial classifier's metadata symmetry is observable only on the unreachable rename-from-metadata edge case.

**Test coverage:** 1440 passing total at v1.5.1. +41 over v1.5.0's 1399. Per-chunk additions (git-measured `def test_` adds): Chunk 01 +24 (`TestParseBuildPlanFrontmatterScope` +12 incl. HTML-comment-then-frontmatter fixtures, `TestDetectActiveScope` +4, `TestRegenViewsScopeFilter` +5 incl. production-shape + scoped-plan-with-no-matching-entries cases, `TestCollectShippedChunks` +3 scope cases), Chunk 02 +4 (`TestCriticSkillDenyPatterns`), Chunk 03 +6 (`TestComputeVerifyResolutionsScopeSubcommand`), Chunk 04 +7 (`TestChunkTypeParseErrorSurfaces` +2, `TestClassifyTrivialChangeMetadataSymmetry` +5, plus one rewrite-in-place that doesn't change count). Sum = 41, matches git-measured delta from `d2b8af4`..HEAD. Cumulative review confirmed via verify-resolutions on every chunk after fixes — every prior BLOCKING/WARNING explicitly addressed.

**Dogfood:** Chunk 01's fix is dogfooded by this very release — `regen-views` against the v1.5.1 plan correctly flips exactly chunks 01-04 to `[x]` and leaves v1.5.0 and v1.4 entries untouched (proved by the per-chunk regen results: each chunk's commit flipped exactly its own checkbox).

**Critic-resolution audit:**
- **Chunk 01:** chunk-mode → 3 BLOCKING (HTML-comment-skip parser bug; YAML null literal handling; `verify-chunk-refs` failed on `tools/lib/views.py:116` ref) + 2 WARNING (test-fixture parity; plan-vs-implementation divergence). All fixed inline. verify-resolutions re-review → 0 BLOCKING, 1 WARNING (doc-drift in plan deliverables vs shipped signature); patched.
- **Chunk 02:** chunk-mode → 1 WARNING (token-budget trim dropped "NO builds" from agents/critic/SKILL.md). Fixed inline. verify-resolutions re-review → 0/0/0 clean. **Known limitation:** the four `!Bash(pytest*)` deny patterns added to skill `allowed-tools` are NOT structurally enforced by Claude Code (confirmed by Chunk 04's Critic invoking pytest successfully). The prose remains, the patterns serve as documentation, and the existing allow-list IS restrictive. Filed to backlog as a v1.5.1 follow-up — fix-shape involves project-level `permissions.deny` or harness-side enforcement.
- **Chunk 03:** chunk-mode → 0 BLOCKING / 0 WARNING / 0 NOTE. Clean first pass.
- **Chunk 04:** chunk-mode → 1 BLOCKING (build-plan refs trip verify-chunk-refs on line-numbered backticked tokens) + 1 WARNING (Critic ran pytest despite Chunk 02's deny patterns — the smoking gun for the Chunk 02 limitation above). BLOCKING fixed; WARNING filed to backlog. verify-resolutions re-review → 0/0/0 clean.

**Backlog items closed:** "`regen-views` doesn't filter by `scope=`" (2026-05-21), "Tighten Critic's tool restriction — block pytest invocation" (2026-05-19, partial — see Chunk 02 known limitation), "Expose `_compute_verify_resolutions_scope` as a CLI subcommand" (2026-05-21), "`_pr_diff_is_trivial` rename src skipped" (2026-05-22), "Surface chunk-Type parse errors to the user" (2026-05-18), "Harden `test_managed_paths_committed_wip_excluded`" (2026-05-19). Adds one new backlog entry: "v1.5.1 Chunk 02's deny patterns do NOT structurally block pytest invocation" (2026-05-23) — superseding the v1.5.0 "structurally enforced" expectation.

**Known follow-ups (deferred to v1.5.2 or later):**
- The structural enforcement of pytest deny-patterns (see Chunk 02 note above). Most likely fix: project-level `permissions.deny` scoped to the Critic skill's invocation context, or a wrapper tool. Needs harness-side experimentation.
- The HOME-leak test pattern (`_run` in `TestComputeVerifyResolutionsScopeSubcommand`) where setting HOME=tmp_path causes Python's xcode-shipped `.pyc` cache to write to `$HOME/Library/Caches/com.apple.python/...` and inflate `git ls-files --others`. The fix used in Chunk 03 (HOME outside project_dir) should be propagated to other tests if they set HOME identically.
- Older v1.5 follow-ups carried forward (`base_reviewed` not validated by cumulative gate; metadata-prefix duplication anchor test; banner-line version coupling; cumulative inference mid-build via per-HEAD records; slash-arg override consistency in Critic SKILL).

## 2026-05-23: v1.5.1 Chunk 04 — Three bundled backlog follow-ups

<!-- prawduct: chunks=04 | status=shipped | scope=v1.5.1 -->

**Why:** Three independent surgical fixes bundled to amortize the per-chunk Critic-pass overhead. Each was filed in the backlog and is too small for its own chunk.

**(a) Surface chunk-Type parse errors (backlog 2026-05-18):** `cmd_stop` previously discarded the `error` tuple element from `_parse_build_plan_chunk_type` (`chunk_type, _ = ...`). A typo'd `Type: code-only` (instead of `code`) was silently rejected by the parser; the author never saw the "unknown type: ..." message. Fix: capture the error and, when it begins with `unknown type:`, append `chunk-type-parse-error: ...` to `waiver_notes` (visible at session-end and in the next briefing). Restricted to `unknown type:` only — `chunk not found` / `missing build-plan` errors indicate fixture-shape issues, not user-actionable typos.

**(b) `_classify_trivial_change` metadata symmetry (backlog 2026-05-22):** Pre-fix, `_is_metadata_path` was applied only to `path` (rename dst) in both `_is_trivial_fileset_eligible` and `_pr_diff_is_trivial` callers. A rename FROM a metadata path went through the classifier with the metadata src untouched. Practically unreachable (metadata paths are gitignored — git rarely produces such renames) but the asymmetry was real. Fix: moved the metadata check INTO `_classify_trivial_change` — returns `None` when EITHER `path` or `src_path` is a metadata path. Both gates now handle metadata uniformly; callers dropped their dst-only filter.

**(c) Harden gitignore-drift test (backlog 2026-05-19):** `test_managed_paths_committed_wip_excluded` previously wrote `.gitignore` from the current `GITIGNORE_ENTRIES` set in the fixture, so `update_gitignore` found nothing to add and the test never exercised the gitignore-mutation path. The next chunk to add a new ignore entry would trigger `.gitignore` mutation and break the assertion. Fix: fixture now writes a deliberately-stale `.gitignore` (omits the first GITIGNORE_ENTRIES line), and the allowed-set in the assertion explicitly includes `.gitignore`. Sanity assertions verify the omitted entry was re-added.

**Tests:** new `TestChunkTypeParseErrorSurfaces` (+2), new `TestClassifyTrivialChangeMetadataSymmetry` (+5), `test_managed_paths_committed_wip_excluded` rewritten in-place. Full suite 1440/1440.

**Critic:** chunk-mode → 1 BLOCKING (build-plan refs trip verify-chunk-refs: line-numbered backticked paths like `tools/product-hook:2321`), 1 WARNING (Critic sandbox didn't block pytest invocation despite v1.5.1 Chunk 02's deny patterns — out-of-scope for Chunk 04; filed to backlog). BLOCKING fixed by rewriting the offending references; verify-resolutions re-review → 0/0/0 clean.

**Backlog:** closes (a) "Surface chunk-Type parse errors to the user" (2026-05-18), (b) "`_pr_diff_is_trivial` applies `_is_metadata_path` to dst path only — rename src skipped" (2026-05-22), (c) "Harden `test_managed_paths_committed_wip_excluded`" (2026-05-19). Adds new entry: "v1.5.1 Chunk 02's `!Bash(pytest*)` deny patterns ... do NOT structurally block pytest invocation" (2026-05-23).

## 2026-05-23: v1.5.1 Chunk 03 — Expose `compute-verify-resolutions-scope` as CLI subcommand

<!-- prawduct: chunks=03 | status=shipped | scope=v1.5.1 -->

**Why:** Defense-in-depth gap surfaced by v1.5 Chunk 02 NOTE. The widening-threshold demotion logic lived inside the stop-hook helper `_compute_verify_resolutions_scope`; the Critic agent computed verify-resolutions scope from SKILL.md prose. If the agent misapplied the prose, it would write a findings file with a wrong `files_reviewed` set and the gate's subset check would accept it (gate enforces only subset, not widening). Two independent computations of the same rule is a drift waiting to happen.

**What:** New `tools/product-hook compute-verify-resolutions-scope` subcommand — a thin CLI wrapper around the canonical `_compute_verify_resolutions_scope` helper. Output format: stdout = newline-separated file paths (the scope union); stderr = one reason line. Exit codes: 0 = scope computed (use the files); 1 = cannot compute (missing prior findings, no `commit_reviewed`, unresolved commit, no actionable findings, git failure, invalid files_reviewed); 2 = scope widened past `len(delta) > 2 * len(prior) + 5`. Fail-safe direction: any exit ≠ 0 → Critic falls back to `/critic chunk` or `/critic final`.

Critic SKILL surfaces updated to call the subcommand instead of computing scope from prose: `agents/critic/review-cycle.md` (canonical), `templates/critic-review.md`, `.prawduct/critic-review.md`. Both Critic skill `allowed-tools` frontmatters (`.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`) gain the narrow permission `Bash(python3 tools/product-hook compute-verify-resolutions-scope)` — exact subcommand string, no wildcard, preserving the v1.5.1 Chunk 02 deny-list discipline.

**Tests:** new `TestComputeVerifyResolutionsScopeSubcommand` in `tests/test_product_hook.py` (+6). Covers each exit path (0/1/2 across four reason categories) plus a parity test asserting subcommand stdout matches the helper's return value exactly — guards against the two paths drifting on every future change. Full suite 1433/1433.

**Critic:** chunk-mode → 0 BLOCKING / 0 WARNING / 0 NOTE. Clean first pass.

**Backlog:** closes "Expose `_compute_verify_resolutions_scope` as a CLI subcommand for the Critic agent" (2026-05-21).

## 2026-05-23: v1.5.1 Chunk 02 — Critic `allowed-tools` deny-list (block pytest)

<!-- prawduct: chunks=02 | status=shipped | scope=v1.5.1 -->

**Why:** Recurring violation of memory rule `feedback_critic_no_test_execution.md` ("Critic should not run tests"). Wave 2 cumulative-Critic invoked pytest despite the prose. Root cause: with `permissions.allow` `Bash(python3:*)` at the project level (settings.local.json), the prose-only restriction is unenforceable.

**What:** Added four `!Bash(...pytest...)` deny patterns to `allowed-tools` in both Critic skill surfaces (`.claude/skills/critic/SKILL.md` for the framework's own Critic, `templates/skill-critic.md` for product-distributed skills). Patterns: `!Bash(pytest*)`, `!Bash(python -m pytest*)`, `!Bash(python3 -m pytest*)`, `!Bash(* python -m pytest*)`. Prose stays in all five Critic surfaces (`agents/critic/SKILL.md`, `templates/critic-review.md`, `.prawduct/critic-review.md`, plus the two skills above) as defense-in-depth.

**Audit (per plan):** Catalogued current Critic Bash patterns — `Bash(git *)`, `Bash(wc *)`, `Bash(python3 tools/product-hook test-status)`, `Bash(python3 tools/product-hook verify-chunk-refs *)`, `Bash(python3 tools/product-hook infer-critic-mode *)`. None match pytest patterns — deny additions cause zero legitimate-use regression.

**Tests:** new `tests/test_critic_skill_metadata.py` (+4). Asserts all four deny patterns present in both surfaces, existing legitimate tools preserved, framework/template deny-sets equivalent (catches drift). Total suite: 1427/1427 passing.

**Memory:** updated `feedback_critic_no_test_execution.md` with "Structurally enforced as of v1.5.1" + the four deny patterns inline.

**Critic:** chunk-mode → 0 BLOCKING, 1 WARNING (dropped "NO builds" from agents/critic/SKILL.md token-budget trim). Fixed inline. verify-resolutions re-review → clean.

**Backlog:** closes "Tighten Critic's tool restriction — block pytest invocation" (2026-05-19).

## 2026-05-23: v1.5.1 Chunk 01 — `regen-views` scope-aware Status flipping

<!-- prawduct: chunks=01 | status=shipped | scope=v1.5.1 -->

**Why:** Active v1.5 bug. `collect_shipped_chunks` unioned every `chunks=` tag across all change-log entries, ignoring `scope=`. v1.4 chunks 05/06/07 share IDs with v1.5 chunks 02/05/06/07; every `regen-views` run would re-flip the wrong checkboxes, so v1.5 chunks were marked `[x]` by hand with an HTML-comment warning telling builders not to run regen. First Tier-1 item in the v1.5.1 backlog-followups plan.

**What:** Three new helpers in `tools/lib/views.py`. (1) `_parse_build_plan_frontmatter_scope(content)` reads `scope:` from a build-plan's YAML frontmatter, tolerating the production shape (leading HTML comment block before the opening `---`) and treating YAML null literals (`null`/`NULL`/`~`/empty) as absent. (2) `_detect_active_scope(build_plan_content, change_log_content=None)` resolves the active scope: frontmatter wins; otherwise the most-recent change-log entry's `scope=` tag; otherwise None (fail-safe). (3) `collect_shipped_chunks(entries, scope=None)` filters by scope when set, preserves legacy unfiltered union when None. `build_status_view` calls `_detect_active_scope` and threads the result through.

**Backward compatibility:** Products without `scope:` frontmatter and change-logs without `scope=` tags get the legacy unfiltered union — zero behavior change. `templates/build-plan.md` ships `scope: null` as the documented "opt-out" form (parser returns None).

**Tests:** +20 covering `TestCollectShippedChunks` scope cases (+3), `TestParseBuildPlanFrontmatterScope` (+12, including 4 HTML-comment-then-frontmatter fixtures that mirror every real build-plan), `TestDetectActiveScope` (+4), `TestRegenViewsScopeFilter` (+5, including the production shape and the "scoped plan with no matching entries yet" no-op case). Full suite 1423/1423 passing.

**Dogfood:** Running `regen-views` against this very v1.5.1 plan after Chunk 01 lands correctly leaves all v1.5.1 chunks `[ ]` (no v1.5.1-scoped entries yet other than this one); v1.4 and v1.5.0 entries no longer bleed through.

**Critic:** chunk-mode initial review → 3 BLOCKING (HTML-comment-skip parser bug; YAML null literal handling; `verify-chunk-refs` failed on `tools/lib/views.py:116` ref). All three resolved + plan deliverable text patched to match the shipped signature. verify-resolutions re-review → 0 BLOCKING, 1 WARNING (doc-drift only); WARNING also patched. Backlog item "`regen-views` doesn't filter by `scope=`" (2026-05-21) resolved.

## 2026-05-22: v1.5.0 — Critic proportionality (release)

<!-- prawduct: chunks=00,01,02,03,04,05,06,07 | release=v1.5.0 | status=shipped | scope=v1.5 -->

**Why:** v1.5 closes the user-feedback loop opened in late v1.4 — "Prawduct is too onerous." Three coupled symptoms drove the work: (1) users were instructing Claude to *defer Critic until the very end* because per-chunk Critic latency compounded; (2) the three-mode caller burden (`chunk`/`final`/`cumulative`) produced frequent "wrong mode" complaints — mistakes cost a full re-run; (3) a one- or two-line resolution to a Critic finding paid full ~8-min re-review latency to confirm. v1.5 ships three coupled fixes — inference-first invocation, a `verify-resolutions` delta mode, and a `Type: trivial` chunk type with structural enforcement — that move proportionality from a per-call discipline ("pick the right mode and hope for the best") to a framework property ("the framework picks; the framework narrows; the framework enforces"). The three threads compose: inference picks `verify-resolutions` automatically when the delta since the last review is just a fix; `Type: trivial` gates the per-chunk Critic *and* the PR-boundary cumulative-Critic gate; explicit args still override at every layer for back-compat.

**What — Thread A (Mode inference):** `/critic` with no arguments calls `tools/product-hook infer-critic-mode` and picks one of four modes from git state + build-plan position. Four-rule precedence (`verify-resolutions > cumulative > final > chunk`); each rule emits a verbatim rationale string recorded as `mode_chosen_by` in the findings file. Explicit `$ARGUMENTS` records `mode_chosen_by: "explicit-args"` and bypasses inference (back-compat for product repos that always pass a token). Fail-safe paths: missing helper → `final|fallback-no-tools-lib`; unrecognized token → `final`. Surfaces touched: new `tools/lib/critic_mode.py` module (416 lines, stdlib-only); new `tools/product-hook infer-critic-mode` subcommand (kept the helper out of Critic SKILL `allowed-tools` Bash escape hatches); `agents/critic/SKILL.md`, `.claude/skills/critic/SKILL.md`, `templates/critic-review.md`, `templates/skill-critic.md`, `.prawduct/critic-review.md` all updated; `methodology/building.md` Critic-invocation paragraph rewritten.

**What — Thread B (Trivial-code fast-path):** New chunk `Type: trivial` lands with **two enforcement layers** that make over-declaration loud, not silent. Layer 1 — `_is_trivial_fileset_eligible(project_dir)` enforces catastrophic-blast-radius bounds: no edits under `agents/`, `methodology/`, or `templates/`; no `CLAUDE.md` edit; no test-file deletions; no new files. Reason strings name the specific bound for actionable stop-hook messaging. **Size is intentionally not bounded** — trivial is a semantic claim (an 80-LOC project-wide rename qualifies; a 5-line state-machine change does not). Layer 2 — `_parse_build_plan_chunk_trivial_rationale` extracts a required `**Trivial because:**` field; empty/absent → BLOCKING. Critic Goal 3 gains a `Type: trivial`-conditional sub-check: rationale-vs-diff fit (claim "rename" but diff adds new function definitions → BLOCKING; low-information rationale "small change" → WARNING). PR-boundary `_pr_diff_is_trivial` walks every commit in `merge-base...HEAD` through the same shared classifier (`_classify_trivial_change`); when a PR is composed entirely of fileset-eligible commits, `/pr create` Step 1c skips cumulative-Critic + reviewer + evidence-verify and notes the skip in the PR description. Stop-hook Gate 3 honors the same skip for cross-session work. Same fail-closed posture as doc-only.

**What — Thread C (`verify-resolutions` delta mode):** Fourth Critic mode. Reads `.prawduct/.critic-findings.json`, extracts files referenced by prior BLOCKING+WARNING findings, adds files changed since `commit_reviewed` (new findings-schema field added in Chunk 01), runs Goals 1-3 on the union. Demotion criterion: `len(new_files) > 2 * len(prior_finding_files) + 5` → demotes to full review and records the demotion. Stop-hook gate accepts a verify-resolutions findings file only when the chunk diff is a subset of the verify scope; otherwise emits a clear BLOCKING message demanding `/critic chunk` or `/critic final`. Fail-safe: missing prior findings or absent `commit_reviewed` → falls through with a recommendation message. Dogfooded three times during v1.5 build (Chunks 02, 03, 06) — each follow-up fix went from ~8 min cumulative re-review to ~1-2 min single-pass clean.

**Backlog items closed:** "Critic `verify-resolutions` / delta mode for follow-up fixes" (2026-05-20, removed in Chunk 02 when the feature shipped). "Small-bugfix proportionality (no code-change escape hatch from review gates)" — never literally in `backlog.md`; carried as v1.5 plan motivation, resolved by Thread B's `Type: trivial`. "Propagate `verify-resolutions` mode to `templates/skill-critic.md` (Chunk 02 gap)" — removed in Chunk 06 when deliverable 6 propagated the four-mode vocabulary to the product entry SKILL template.

**Backward compatibility:** Product repos that explicitly invoke `/critic chunk` / `/critic final` / `/critic cumulative` continue to work unchanged — explicit `$ARGUMENTS` bypasses inference at every layer; `mode_chosen_by: "explicit-args"` records the override path. Findings-schema additions (`commit_reviewed`, `base_reviewed`, `mode_chosen_by`) are all optional — old findings files validate as before. No migration required. `tools/lib/critic_mode.py` is shipped as part of the framework; product repos missing the module (e.g., on stale syncs) get a `final|fallback-no-tools-lib` recommendation rather than a crash.

**Release shape:** Eight chunks across the standard v1.x cadence — Chunk 00 (SKILL.md token-budget pre-trim, 524 tokens recovered), 01 (findings schema), 02 (verify-resolutions mode + gate), 03 (inference), 04 (`Type: trivial` + structural enforcement), 05 (Critic protocol for trivial + PR fast-path), 06 (methodology + template refresh — inference-first narrative, four-mode table), 07 (this entry — version bump, change-log, regen-views, PR creation). The release itself dogfoods the new gates: `/pr create` exercises the cumulative-Critic gate against the bundle that built it; `/critic` (no args) at end-of-plan picks `final` automatically — first user-facing proof of inference; `check-pr-trivial` correctly disqualifies this branch (touches `agents/`, `methodology/`, `templates/`) — proof the fast-path's catastrophic-blast-radius bounds work as intended.

**Test coverage:** 1399 passing total at v1.5.0. +113 over v1.4.0's 1286 (per-chunk: Chunk 01 +9, Chunk 02 +21, Chunk 03 +37, Chunk 04 +27, Chunk 05 +19). New test files: `tests/test_critic_mode_inference.py` (Chunk 03 — 37 tests covering every rule's win + non-win conditions, rationale-string format, subcommand entrypoint, schema validator). New test classes: `TestVerifyResolutionsMode` (Chunk 02, 20 tests); `TestFindingsSchemaCommitReviewed` (Chunk 01, 9 tests); `TestTrivialFilesetBounds`/`TestTrivialRationalePresence`/`TestTrivialStopHookGate` (Chunk 04, 26 tests in three new classes; +1 to existing `TestParseBuildPlanChunkType` = +27 net); `TestPrDiffIsTrivial`/`TestCheckPrTrivialSubcommand`/`TestRationaleVsDiffAnchors` (Chunk 05, 19 tests). One known xdist-flake in `TestMatchHistoricalRender::test_depth_cap_respected` (passes standalone at 30.57s right against 30s timeout; full suite clean when sync runs sequentially via `-n0` — unrelated to v1.5 work).

**Token-budget headroom remaining:** `agents/critic/SKILL.md` at 3045 / 3050 tokens after Chunks 00/02/03/05 collectively consumed the 250-token headroom that Chunk 00's trim reserved. `methodology/building.md` at 4446 / 4450 tokens after Chunks 03 (+50 for inference paragraph) and 06 (trimmed Modes block to fit). Both files end v1.5 within budget. Future thread work on the Critic SKILL or building methodology will need another pre-trim chunk on the v1.4-Chunk-00 / v1.5-Chunk-00 pattern.

**Known follow-ups (NOTE-level, carried to backlog or addressed in v1.5.1):**
- `_pr_diff_is_trivial` applies `_is_metadata_path` to dst path only — rename src skipped. Practically unreachable since metadata paths are gitignored; fix-shape captured (Chunk 05 N3).
- `regen-views` doesn't filter by `scope=` when flipping build-plan Status checkboxes. Hit during v1.5 (Chunks 02, 04, 06 marked their Status `[x]` by hand). Workaround: by-hand edit + `<!-- don't run regen-views -->` comment in the build-plan Status section until scope-filtering lands (backlog).
- Expose `_compute_verify_resolutions_scope` as a CLI subcommand for the Critic agent (defense-in-depth gap — currently the agent reimplements the widening threshold from SKILL.md prose). Filed Chunk 02.
- Re-enable cumulative inference mid-build by recording per-HEAD cumulative records (Chunk 03 spec deviation — the clean-tree guard prevents mid-chunk-3-of-5 from silently demoting `chunk` reviews to 4-10 min `cumulative` runs at every commit; longer-term, per-HEAD cumulative records would let inference re-fire cleanly).
- Slash-arg override layer in the Critic SKILL is inconsistent — Chunk 07's `/critic final` invocation ran inference (`mode_chosen_by: "rule-4 chunk"`) instead of honoring the explicit arg, while a subsequent `/critic verify-resolutions` invocation correctly recorded `"explicit-args"`. Methodology (Chunk 06) describes the slash arg as an override on top of inference; the SKILL prompt path doesn't consistently apply that contract. Filed for v1.5.1 — first-fix candidate since the override is the documented escape valve when inference picks wrong.
- `.claude/scheduled_tasks.lock` (scheduler process lock, untracked) is neither gitignored nor in `_METADATA_PREFIXES`, so its presence breaks rule-2 cumulative inference's clean-tree guard. Discovered while debugging why `infer-critic-mode` picked `chunk` instead of `cumulative` after the Chunk 07 commit. Fix: add to `.gitignore` and to both metadata-prefix tuples (mirror requirement noted in `tools/lib/critic_mode.py:74-82`).
- `base_reviewed` populated by Chunk 01's schema addition but not validated by the cumulative gate (`cmd_check_cumulative_critic`) — after a rebase, a stale cumulative record's `base_reviewed` could no longer match `git merge-base`. Defense-in-depth check for v1.5.1 (Critic NOTE).
- Anchor test for `_METADATA_PREFIXES` duplication between `tools/lib/critic_mode.py` and `tools/product-hook` — comment block flags manual-sync requirement; a one-test assertion that the two tuples are equal would catch drift without changing the architectural choice (Critic NOTE).
- Banner-line version coupling — Chunk 07's banner-text update (the third "★ New:" line) was hand-edited; nothing structurally couples banner content to release-tag content. Low-cost backlog: a `regen-views` extension that reads the latest `release=` change-log entry's headline could regenerate the banner line atomically with the version bump.

**Critic-resolution notes (final-mode chunk-07 + cumulative-mode v1.5 bundle):** Chunk-mode review (slash arg `final` silently demoted to inference rule-4 — see follow-up bullet above) returned 1 WARNING / 2 NOTE. W1 (`VERSION` file not bumped — only `.claude/settings.json` banner was) fixed inline — the canonical version file is what downstream product repos read via `sync-manifest.framework_version`; bidirectional staleness warning wouldn't fire without it. N1 (`tools/lib/critic_mode.py` line-count claim "~270" vs actual 416) fixed inline. N2 (Chunk 04 test-count phrasing ambiguity "26 vs +27") fixed inline by adding the parenthetical "26 tests in three new classes; +1 to existing `TestParseBuildPlanChunkType` = +27 net". Verify-resolutions pass returned 0/0/0 clean against the fixes. Cumulative review (`/critic cumulative`, explicit-args override) returned 1 WARNING / 3 NOTE. W1 (stale duplicate `.prawduct/artifacts/v1.5-critic-proportionality-plan.md` with all `[ ]` checkboxes diverging from the live `build-plan.md` `[x]` state) fixed inline by marking the v1.5 plan file's Status to all `[x]` and adding a context note that the file is the original-proposal historical record. N2 (banner third line still pitched v1.4's `/prawduct-doctor`) fixed inline — now reads "★ New in v1.5: /critic infers its own mode + Type: trivial fast-path". N3 (`base_reviewed` not validated by cumulative gate) + N4 (anchor test for metadata-prefix duplication) added to the follow-ups list above. 

**What's next (v1.6 sketch):** Two strong candidates surface from v1.5's dogfood — (a) scope-filtering for `regen-views` (the by-hand Status workarounds during v1.5 made the cost visible); (b) per-HEAD cumulative records to re-enable mid-build cumulative inference. Both are touch-up shape relative to the proportionality machinery v1.5 just landed. The v1.5.0 release marks the proportionality work as complete on its acceptance criterion — inference + trivial fast-path + verify-resolutions all shipped, dogfooded across the release itself, with no regressions to the existing 1286-test surface.

## 2026-05-22: Chunk 06 — Methodology + template refresh (inference-first, four-mode table)

<!-- prawduct: chunks=06 | status=shipped | scope=v1.5 -->

**Why:** v1.5 Chunks 01–05 landed the proportionality machinery (verify-resolutions mode, no-arg inference, `Type: trivial` with structural enforcement, Critic Goal 3 rationale-vs-diff check, `/pr` trivial fast-path). Prose surfaces still spoke the v1.4 vocabulary: "Each chunk declares `Critic mode: chunk | final`", "fail-safe default if the field is absent", no mention of inference as the canonical path, no mention of `cumulative` or `verify-resolutions` in the per-chunk authoring narrative. This chunk closes the doc gap — narrative now leads with `/critic` (no args) → inference; explicit `Critic mode:` field is reframed as override; all four modes named consistently across methodology, agent SKILL files, and templates.

**What:**

1. **`methodology/building.md` Modes section.** Expanded from two-mode block (`chunk`/`final`) to a four-mode block with inference-as-default. Leads with: "`/critic` (no args) infers mode from git + build-plan state via `tools/product-hook infer-critic-mode`. Inference is the default path; `Critic mode:` in the build plan is the override, and a slash-command argument is the per-invocation override on top of that." Each of `chunk`/`final`/`cumulative`/`verify-resolutions` gets a one-line summary (Goals run, scope, target wall-clock). Fail-safe rephrased: "If inference fails or an explicit mode is unrecognized → `final`." (The Critic review step at line 87 already leads with inference from Chunk 03 — this update brings the Modes block below into alignment.)

2. **`methodology/planning.md` "Critic Mode Per Chunk".** Reframed `Critic mode:` as **optional** when inference suffices; explicit declaration remains the override. Heuristic table updated: inference picks `chunk` for non-final chunks and `final` for the last chunk — no declaration needed for the common case. New override examples: forward to `final` on an early architectural-keystone chunk; forward to `cumulative` (via `Type: cumulative-final`) on the last chunk of a multi-chunk plan. Trivial-chunk bullet now points to `Type: trivial` for bounded mechanical code changes as an alternative to `.gates-waived`. Fail-safe paragraph clarified: inference falls back to `final` when it can't anchor a confident pick; both layers fail safe to thoroughness.

3. **`agents/critic/review-cycle.md` Mode Selection prose.** The Per-Mode Behavior table (line 35) already has four columns from Chunks 02–03; this chunk updates the `## Mode Selection` narrative above it. Rewrote to name `/critic` (no args) as the canonical caller (records `mode_chosen_by: inference`), and to frame `Critic mode:` and explicit slash arguments as two layers of override. Heuristic block annotated with what inference will pick so authors know when an explicit declaration is worth writing.

4. **`templates/build-plan.md` `Critic mode:` field.** Placeholder line updated from `[pick one: chunk or final]` to `[optional — omit and let /critic infer, or pick one to override: chunk | final | cumulative | verify-resolutions]`. HTML-comment expanded to: (a) say the field is OPTIONAL, (b) explain inference picks the common case, (c) list all four modes with one-line summaries, (d) describe override examples, (e) note the fail-safe path (missing → inference; unrecognized → `final`). The "third mode `cumulative`" parenthetical removed — all four modes are now first-class. Authoring-instructions block (line 177) parallel update: "Critic mode (optional — `/critic` infers from git + plan state; declare only to override)".

5. **`templates/build-governance.md` chunk-close step.** Step 7 (Critic review) rewritten to lead with `/critic` (no args), explain what `infer-critic-mode` does and that the SKILL records `mode_chosen_by` as the helper's verbatim rationale string (or `"explicit-args"` when overridden), and frame the chunk's `Critic mode:` field + slash-command args as the two override layers. Both fail-safe paths (inference fails → `final`; unrecognized token → `final`) called out explicitly.

6. **`templates/skill-critic.md` four-mode propagation (was a backlog item).** Chunk 02 propagated `verify-resolutions` into the framework's own `.claude/skills/critic/SKILL.md` and `templates/critic-review.md` but not into the product entry SKILL template — a gap captured as a backlog item during Chunk 03. Chunk 06's acceptance criterion "all instruction files name the four modes consistently" pulls this in: `argument-hint` frontmatter, Getting-Started step 1 (recognized mode tokens + per-mode behavior summary), and step 7 Output Format (verbose `mode_chosen_by` string) all updated to include `verify-resolutions`. Sentinel test `TestCriticEntrySkillEnumeratesAllModes` tightened — both framework and product entry files now require all four modes; the per-file required-set carve-out the Chunk 03 test added is removed.

**Backlog reconciliation:** Three items resolved.
- "Critic `verify-resolutions` / delta mode for follow-up fixes" — already removed in Chunk 02 (d36cefa) when the feature shipped (carried into the v1.5 plan at 1030ba6 for tracking).
- "Small-bugfix proportionality" — never literally in `backlog.md`; carried as v1.5 plan motivation (plan §40 references it as "PR #41 out-of-scope"). The v1.5 plan itself was the disposition.
- "Propagate `verify-resolutions` mode to `templates/skill-critic.md` (Chunk 02 gap)" — removed in this chunk (deliverable 6 above).

**Test coverage:** Existing rationale-vs-diff anchor tests (`TestRationaleVsDiffAnchors`, 6 cases) continue to anchor cross-file prose contracts. `TestCriticEntrySkillEnumeratesAllModes` (4 cases) tightened — `argument-hint enumerates all modes` and `getting started recognizes cumulative` now run on both framework and product entry paths with all four modes required. Full suite remains at 1399 passing. The Critic's `final`-mode run against this chunk's doc diff is the verification (Goal 4: Coherence — prose now tells a consistent story across `methodology/`, `agents/critic/`, and `templates/`).

**Critic-resolution notes (final-mode review, mode picked by inference rule-3):** Returned 1 BLOCKING / 2 WARNING / 3 NOTE. B1 (three doc surfaces invented a `mode_chosen_by: inference` / `arguments` vocabulary that contradicts the Chunk 03 contract — actual contract is the verbatim rationale string from `infer-critic-mode`, or `"explicit-args"` when overridden) fixed inline across `agents/critic/review-cycle.md`, `templates/build-governance.md`, and `templates/build-plan.md`. W1 (`methodology/planning.md` line 85 listed `cumulative-final` as a `Critic mode:` override example — but `cumulative-final` is a `Type:` value, not a mode value; the four modes are `chunk | final | cumulative | verify-resolutions`) fixed inline — dropped the conflated example, the override examples below already cover the case correctly. W2 (`templates/skill-critic.md` still enumerated only three modes) addressed by extending Chunk 06 scope to fix it (deliverable 6 above) — closes the Chunk 02 backlog item. Three NOTEs (uneven fail-safe documentation, "every gate" claim slightly overstates the trivial fast-path case, positive scope-discipline confirmation) acknowledged; first two flagged for Chunk 07's release-notes pass.

**Second-pass `final` review caught a dogfood gap** — `.prawduct/build-governance.md` (the framework's own synced copy of `templates/build-governance.md`) still carried v1.4 two-mode vocabulary on line 31 because the template-update doesn't auto-render the local copy. Re-ran `python3 tools/prawduct-sync.py .` to render the updated template into `.prawduct/build-governance.md` and refresh the `generated_hash` in `.prawduct/sync-manifest.json`. The `verify-resolutions` pass against the sync-fix diff returned 0 BLOCKING / 0 WARNING / 2 NOTE — third consecutive dogfood proof of the new mode's value, with `mode_chosen_by` correctly recorded as `"explicit-args"` (caller passed the token explicitly via `/critic verify-resolutions`).

**Methodology token budget:** trimming the Modes section's four-mode block to ≤4450 tokens required compacting the closing reference line from `"See agents/critic/review-cycle.md for the per-mode table and .prawduct/critic-review.md (or agents/critic/SKILL.md) for goal definitions"` to `"See agents/critic/review-cycle.md (per-mode table) and .prawduct/critic-review.md (goals)"`. `critic-review.md` substring preserved for the methodology cross-reference sentinel. Final landing: 4446 tokens.

**What's next:** Chunk 07 is cumulative-final — `/critic cumulative` against the v1.5 bundle, release-version bump (1.4.x → 1.5.0), release-notes view regen, and PR creation. The `/pr create` invocation will be itself a dogfood of the v1.5 proportionality work — every gate the new modes touch fires on the bundle that built them.

## 2026-05-22: Chunk 05 — Critic protocol for `Type: trivial` + `/pr` trivial fast-path

<!-- prawduct: chunks=05 | status=shipped | scope=v1.5 -->

**Why:** v1.5 thread B (Trivial-code fast-path; see plan Motivation lines 30-32) completes here. Chunk 04 landed the `Type: trivial` declaration with two machine-enforced layers (file-set bounds + required rationale presence). Both layers are *structural* — they catch catastrophic-blast-radius classes and empty-claim violations without semantic understanding. The judgment backstop — does the rationale's claim actually fit the diff? — needs the Critic, who reads both. Chunk 05 adds the Critic Goal 3 sub-check that closes that loop, and the parallel PR-boundary fast-path that lets a PR composed entirely of fileset-eligible commits skip the cumulative-Critic + PR-reviewer gates (their per-chunk reviews already provided the relevant scrutiny — re-running them adds latency, not signal).

**What:**

1. **Goal 3 sub-check — Rationale-vs-diff fit (`Type: trivial` only).** `agents/critic/SKILL.md` Goal 3 gains a `Type: trivial`-conditional sub-check: read the chunk's `**Trivial because:**` rationale from `build-plan.md` (parser landed in Chunk 04) and compare against the actual diff. Mismatch (rationale "rename" but diff adds new function definitions; rationale "type annotations" but diff modifies control flow; rationale "add logging" but diff changes return values) → **BLOCKING** for scope expansion past the trivial declaration. Low-information rationale (single word; generic phrases like "small change", "easy fix") → **WARNING** ("rationale provides no testable claim"). The file-set bounds (Chunk 04 layer 1) and rationale-presence check (Chunk 04 layer 2) are machine-enforced before the Critic runs — by the time the Critic sees a `Type: trivial` chunk, those layers have passed. The sub-check is the judgment backstop the file-set can't provide. Strong-vs-weak rationale examples already live in `methodology/planning.md`; the Critic prompts anchor expectations there.

2. **Per-Chunk Type Protocol Selector matrix — new `trivial` row.** `agents/critic/review-cycle.md` matrix gains the `trivial` row: Goals 1 (full), 2 (full), 3 (full + rationale-vs-diff sub-check), test-evidence required, stop-hook Critic gate fires. Mirrored in `templates/critic-review.md`. The row makes the per-Type contract visible alongside `code`/`doc-only`/`cleanup`/`designer-handoff`/`cumulative-final`.

3. **PR fast-path — `_pr_diff_is_trivial(project_dir) → (is_trivial, status)`.** Walks `git log --name-status -M --format=%H <base>..HEAD`, applies Chunk 04's path bounds (via the new shared classifier `_classify_trivial_change`) per file in each commit. Returns False on first violating commit with a reason naming the SHA and the specific bound (e.g., `not-trivial: commit a1b2c3d agent-file-edited: agents/foo.md`). Empty diff / no-base / git-failed all fail closed — falls through to full review. **No size bound** — same logic as per-chunk: size isn't the risk axis. **Per-commit walk** (not cumulative) so a commit that adds an `agents/` file then a later commit that removes it is correctly NOT fast-path eligible — the work crossed a catastrophic-blast-radius boundary at least once during the build.

4. **`check-pr-trivial` subcommand.** Thin CLI wrapper paralleling `check-pr-doc-only`. Exit 0 = fast-path eligible (status to stdout); exit 1 = anything else (reason + actionable suffix to stderr). Wired into `_USAGE` and the main dispatcher.

5. **`/pr create` Step 1c — Trivial-code fast-path.** `.claude/skills/pr/SKILL.md` gains Step 1c after Step 1b (doc-only). Exit 0 → skip Steps 2/2b/3/4 (cumulative-Critic gate, operator-verification gate, reviewer agent, evidence verify); jump to Step 5 (create PR), note the skip in the PR description. Exit 1 → proceed to Step 2 (full review). `agents/pr-reviewer/SKILL.md` and `templates/pr-review.md` document both fast-paths so a reviewer invoked under one knows it shouldn't half-skip.

6. **Stop-hook Gate 3 parallel skip.** The session-end PR-review evidence gate (`cmd_stop` in `tools/product-hook`) already short-circuits when the PR diff is doc-only; this chunk adds the parallel trivial check. Cross-session work on a trivial PR doesn't get blocked at session end for missing PR-review evidence — symmetric with `/pr create` Step 1c. If a later session adds non-trivial commits, both checks return False and the gate fires as intended (matches the create-flow contract).

7. **Shared classifier — `_classify_trivial_change`.** Chunk 04's `_is_trivial_fileset_eligible` (working-tree porcelain) and the new `_pr_diff_is_trivial` (per-commit name-status) need identical path rules. Extracted the rule set into a single helper that both call — the stop-hook gate and the PR-boundary gate can't drift apart silently. Refactor preserves Chunk 04's behavior (all 26 trivial-related tests across `TestTrivialFilesetBounds`, `TestTrivialRationalePresence`, and `TestTrivialStopHookGate` still pass).

**Governance checkpoint (per plan §369):** Ran `python3 tools/product-hook check-pr-trivial` against this in-flight v1.5 branch — correctly reports `not-trivial: commit b422828 methodology-edited: methodology/planning.md` and exits 1. The branch touches `agents/`, `methodology/`, and `templates/` (every chunk does — this IS the framework), so the fast-path correctly disqualifies it. Dogfood proof.

**Test coverage:** 1399 passing total (+19 over Chunk 04's 1380; xdist worker timeout race on `test_prawduct_sync.py::TestMatchHistoricalRender::test_depth_cap_respected` filed as known flake — passes standalone at 30.57s right against the 30s timeout, unrelated to this chunk; the full suite is clean when sync is run sequentially via `-n0`). New `TestPrDiffIsTrivial` (9 cases) covers single-trivial-commit pass, many-trivial-commits pass (no size bound), each catastrophic-class violation (`agents/`, `methodology/`, new-file, test-deletion, rename-out-of-tests), empty PR fail-safe, no-base fail-safe. New `TestCheckPrTrivialSubcommand` (4 cases) covers CLI shape (exit 0 + stdout, exit 1 + stderr) for the same scenarios. New `TestRationaleVsDiffAnchors` (6 cases) anchors the rationale-vs-diff prose wording across SKILL.md, review-cycle.md, the critic-review template, the pr-review template, the pr SKILL, and the pr-reviewer SKILL — prose anchors are the contract since the rationale-vs-diff check is Critic-prompt guidance, not a code helper. Total: 9+4+6 = 19 new test methods.

**SKILL.md token budget:** trimmed the Goal 3 sub-check prose from ~250 to ~95 tokens to fit the 3050-token ceiling (chunk 00 reserved 250 tokens of headroom for v1.5 chunks 02, 03, 05; final landing is 3045 — chunks 02+03+05 collectively consumed 245 tokens). Content preserved: rationale-vs-diff check definition, BLOCKING for scope mismatch, WARNING for low-information claims, pointer to `methodology/planning.md` for strong-vs-weak examples.

**Critic-resolution notes (chunk-mode review):** Returned 0 BLOCKING / 0 WARNING / 3 NOTES. N1 (change-log called this "v1.5 thread D" but plan defines only threads A/B/C) fixed inline — corrected to "thread B (Trivial-code fast-path)" per plan Motivation lines 30-32. N2 (claim "all 18 Chunk 04 tests still pass" — actual count is 26 across the three trivial-related classes) fixed inline — corrected number. N3 (metadata-path filter applied to dst only, src skipped in rename rows) backlogged per the Critic's recommendation — practically unreachable since metadata paths are gitignored, fix-shape captured for the future symmetry pass.

**What's next:** Chunk 06 is the methodology + template refresh pass (inference-first narrative, four-mode table). Chunk 07 is cumulative-final — release prep, backlog reconciliation, v1.5.0 PR.

## 2026-05-22: Chunk 04 — `Type: trivial` chunk type + structural enforcement

<!-- prawduct: chunks=04 | status=shipped | scope=v1.5 -->

**Why:** v1.5 thread D — proportionality at the chunk-type axis. Some chunks are semantically simple (project-wide renames, type-annotation passes, learnings-only appends) but currently must pay full `code`-type Critic protocol because no lighter type exists. Adding a `trivial` type without structural enforcement would invite over-declaration (the "small change" misclaim pattern), undoing the proportionality the type is meant to enable. This chunk lands the type AND the two enforcement layers that make over-declaration loud (BLOCKING with a named bound), not silent.

**What:**

1. **`trivial` joins `_BUILD_PLAN_ALLOWED_TYPES`.** `code | doc-only | cleanup | designer-handoff | cumulative-final | trivial`. Parser (`_parse_build_plan_chunk_type`) accepts the new token with no other behavior changes — back-compat held.

2. **Layer 1 — `_is_trivial_fileset_eligible(project_dir) → (eligible, reason)`.** Machine-enforced file-set bounds: chunk diff has no edits under `agents/`, `methodology/`, or `templates/`; no edits to `CLAUDE.md`; no test-file deletions; no new files anywhere. Reason strings name the specific bound that failed (`agent-file-edited: agents/critic/SKILL.md`, `methodology-edited: methodology/building.md`, `template-edited: templates/build-plan.md`, `claude-md-edited: CLAUDE.md`, `test-file-deleted: tests/test_foo.py`, `new-file: src/bar.py`) for actionable stop-hook messaging. Uses session-baseline filtering (mirrors `git_has_session_changes`) so pre-session dirt doesn't count against the chunk. **Size is intentionally not a bound** — trivial is a semantic claim, not a LOC metric; an 80-LOC rename can be trivial, a 5-line state-machine change cannot.

3. **Layer 2 — `_parse_build_plan_chunk_trivial_rationale(prawduct_dir, chunk_id) → (rationale, error)`.** Extracts the required `**Trivial because:**` field from the chunk's build-plan section. Empty or absent → `missing-rationale: Type: trivial requires non-empty **Trivial because:** field`. Multi-line continuation supported (lines without list-item / heading prefix join until the next field). Section discovery mirrors `_parse_build_plan_chunk_type` — name-anchored on `### Chunk <id>:` with leading-zero tolerance; fenced code blocks skipped.

4. **Stop-hook gate dispatch — `Type: trivial` enforcement.** When the current chunk's `Type:` is `trivial`, the stop hook runs both checks. Any failure emits BLOCKING with the specific reason: `TYPE: TRIVIAL — declared but <reason>. Either fix the violation or change Type to \`code\`.` The chunk is treated as `code` for gate purposes regardless — `trivial` is NOT a Critic-skip carveout (only `designer-handoff` is); the Critic gate still applies on top. **The trivial check does not honor the doc-only skip** — bounds like "no edits under agents/" matter even when the diff is empirically all-.md (the agents/ tree itself is pure prose); doc-only only carves out the Critic protocol, not the trivial-declaration contract.

5. **Template + methodology refresh.** `templates/build-plan.md` Type field comment documents `trivial` with the file-set bounds and the required rationale field; adds `**Trivial because:**` to the chunk template (required-when-trivial, omit-otherwise) with strong-vs-weak rationale examples. `methodology/planning.md` "Choosing a Chunk Type" gains the `trivial` entry with the two-layer enforcement breakdown, the size-is-not-bounded principle, the over-declaration warning, and strong/weak rationale examples.

**Pre-impl audit (last 10 prawduct chunks):** 8 of 10 fail-closed on file-set alone (chunks edit `agents/`, `methodology/`, `templates/`, or add new files — all framework-shape changes correctly excluded). 2 chunks pass file-set (F5a Chunk 11 sync auto-commit; F5b Chunk 12 settings migration) but neither is *semantically* trivial — both add new behavior. **Validates the design**: file-set is necessary but not sufficient; rationale + Critic Goal 3 (Chunk 05) is the semantic backstop. Outside the chunk-tagged set, the cleanest historical trivial candidate is `d23053b` (single-file `.prawduct/learnings.md` append) — rationale would be `"appends two learning entries; no code, no tests, no behavior."` Locked rules match the plan; no spec deviations.

**Test coverage:** 1380 passing total (+27 over Chunk 03's 1353; 2 pre-existing xdist-flakes in `test_prawduct_sync.py::TestMatchHistoricalRender::test_depth_cap_respected` — pass in isolation, unrelated). New `TestTrivialFilesetBounds` (13 cases) covers eligible diff regardless of size, each bound violated separately with actionable reason, metadata-path filtering, baseline-filter excluding pre-session dirt, no-git fail-open, rename-target bounds-checking, AND rename-out-of-tests (closes the gap where source-path examination would be needed). New `TestTrivialRationalePresence` (8 cases) covers single-line + multi-line + empty + whitespace-only + sibling-isolation + missing-chunk + missing-plan. New `TestTrivialStopHookGate` (5 cases) covers eligible passes + each failure mode produces BLOCKING with named reason. `TestParseBuildPlanChunkType` extended with a `trivial` case (+1). Total: 13+8+5+1 = 27 new test methods.

**Critic-resolution notes (chunk-mode review):** Returned 0 BLOCKING / 2 WARNINGS / 3 NOTES. W1 (stale test evidence) fixed by re-running pytest. W2 (change-log claimed +38 tests, actual was +26) fixed inline — totals were consistent (1353+26=1379), only the delta string was wrong; corrected to +27 after adding the rename-out test below. N1 (docstring claim "no new files anywhere" slightly broader than `A`/`??` enforcement) fixed by tightening the docstring to name the porcelain statuses explicitly. N2 (`git mv tests/x src/x` bypasses the test-deletion check — destination-only examination) fixed inline by also examining the source path of `R` renames; +1 test (`test_rename_out_of_tests_fails`). N3 (literal "100-LOC eligible diff fixture" from spec is covered in spirit by `test_clean_eligible_diff_passes` proving no-LOC-computation) acknowledged as informational.

**What's next:** Chunk 05 adds Critic protocol for `Type: trivial` (Goals 1-3 + rationale-vs-diff fit check) and the `/pr` trivial fast-path. The rationale field landed here is the input the Critic compares against the actual diff in Goal 3.

## 2026-05-22: Chunk 03 — `/critic` no-arg mode inference

<!-- prawduct: chunks=03 | status=shipped | scope=v1.5 -->

**Why:** Last piece of v1.5 thread C. With Chunks 01 (`commit_reviewed` anchor) and 02 (`verify-resolutions` mode) shipped, the builder still had to declare `Critic mode:` in every chunk and pass it explicitly to `/critic`. This chunk collapses the four-mode caller burden by inferring mode from git + build-plan state. Explicit args still win — the override path is preserved.

**What:**

1. **New module `tools/lib/critic_mode.py`.** Single function `infer_mode(project_dir, args) → (mode, rationale)` walks four precedence rules: (1) `verify-resolutions` when prior findings have BLOCKING/WARNING with resolvable `commit_reviewed` AND uncommitted diff is a non-empty subset of prior `files_reviewed` (fix-in-progress signal); (2) `cumulative` when working tree is clean AND branch is ≥2 commits ahead of base AND no cumulative-mode record covers current HEAD; (3) `final` when last unchecked chunk of a multi-chunk plan is in progress, OR no plan + uncommitted diff ≥5 files; (4) `chunk` when an active build plan grounds the choice, `final` otherwise (fail-safe — no plan means no chunk to scope against). Re-exported via `tools/lib/__init__.py`. Stdlib-only per plan constraint (helpers `_count_build_plan_chunks`, `_is_metadata_path`, `_get_uncommitted_code_files` re-implemented locally to avoid pulling product-hook into the import surface).

2. **Spec deviation — clean-tree guard on rule 2 (cumulative).** Literal spec says "branch ≥2 ahead + no cumulative record" with no working-tree check. Implemented WITH a clean-tree guard so the rule doesn't over-fire mid-chunk-3-of-5 (which would silently demote `chunk`-mode reviews to 4-10 min `cumulative` runs at every commit, undoing the proportionality motivation that drove the whole thread). Documented at length in the module docstring; rule-2 fixture tests both the win condition and the dirty-tree non-fire.

3. **`infer-critic-mode` subcommand.** New `python3 tools/product-hook infer-critic-mode [args]` wraps the helper via lazy import — keeps the Critic SKILL's `allowed-tools` structurally bounded (no `Bash(python3 -c *)` escape hatch). Output is `<mode>|<rationale>` on stdout. Fail-safe: when `tools/lib/` is absent (legacy product repos that haven't received the inference helper), prints `final|fallback-no-tools-lib` and exits 0 — never crashes the Critic invocation. Resolves Chunk 02's deferred NOTE about helper-as-CLI defense-in-depth (same pattern, applied to inference instead of `_compute_verify_resolutions_scope`).

4. **Findings schema — `mode_chosen_by` field.** `validate_critic_findings` accepts optional `mode_chosen_by` string (the verbatim rationale from `infer-critic-mode`, or `"explicit-args"` when `$ARGUMENTS` overrode). Rejects empty / whitespace-only / non-string values — writer drift surfaces at validation, not later. Post-hoc introspection: when inference picks the wrong mode, `mode_chosen_by` shows which rule fired so the rules can be tuned.

5. **Docs propagated across all five Critic surfaces.** `agents/critic/SKILL.md` Step 1 + Output Format (now 3030 tokens — under 3050 budget after second trim pass when Critic flagged the fail-safe overstatement). `.claude/skills/critic/SKILL.md` Getting Started Step 1 + allowed-tools (`infer-critic-mode` added) + argument-hint (`(omit for inference) | ...`). `templates/critic-review.md` Setup Step 1 + Output Format `mode_chosen_by` field. `templates/skill-critic.md` parallel update (verify-resolutions still absent from product entry — Chunk 02 gap, not Chunk 03's to fix). `.prawduct/critic-review.md` sync-propagated, manifest hash refreshed. `methodology/building.md` Critic-invocation paragraph rewritten to lead with inference and frame explicit args as the override path; sentinel ceiling 4400 → 4450 with rationale.

**Dogfood validation:** Chunk-mode Critic returned 0 BLOCKING / 2 WARNINGS (W1: fail-safe prose overstated implementation — docs claimed universal fall-through to `final` but rule-4 returned `chunk` for active plans; W2: stale test evidence). Both warnings legitimate. W1 fixed by tightening doc prose across all five surfaces to describe the actual `chunk`-for-active-plan / `final`-otherwise behavior — and by realigning rule-4 to return `final` for the no-plan idle case (where chunk-mode has no plan to scope against). W2 fixed by re-running pytest and writing fresh `.test-evidence.json`. Subsequent `/critic verify-resolutions` against the warning-fix diff anchored at Chunk 02's commit, scope was identical to the prior pass's `files_reviewed` (no new commits), and returned 0 findings — second consecutive proof that verify-resolutions cuts re-review latency exactly as designed.

**Inference dogfooding (incidental):** at the moment of running `/critic chunk` for Chunk 03, the inference helper itself picked `chunk` mode (rule-4: active plan, prior chunks committed). Matched the explicit declaration in the build plan — first end-to-end proof that inference agrees with author-intent for the canonical mid-build case.

**Test coverage:** 1353 passing (+37 over Chunk 02's 1316). New `tests/test_critic_mode_inference.py` covers each rule's win + non-win conditions (`TestRule1VerifyResolutions` through `TestRule4ChunkDefault`), explicit-args override (`TestExplicitArgsOverride`), rationale-string format (parameterized across all four rules), the `infer-critic-mode` subcommand entrypoint (`TestInferCriticModeSubcommand`), and the schema validator's `mode_chosen_by` acceptance + rejection (`TestValidatorAcceptsModeChosenBy`). Real-git fixtures (`_init_repo` / `_commit` / `_checkout_new_branch`) — mock git would diverge on porcelain status, rev-parse, rev-list which the helper relies on. Sentinel sibling: `tests/preferences/test_critic_skill_structure.py` updated from substring-match argument-hint check to per-token enumeration check (preserves the contract while supporting the new `(omit for inference) | ...` prefix). `tests/test_v5_methodology.py` budget bumps with documented rationale.

**Backlog (carried):** N2 (Chunk 02 gap — propagate `verify-resolutions` mode to `templates/skill-critic.md` argument-hint, mode list, and output snippet so products see all four modes once they sync) is filed for Chunk 02 follow-up — Chunk 03 deliberately did not expand scope to fix it, but the inference work surfaced the gap when updating the argument-hint sentinel test.

## 2026-05-21: Chunk 02 — `/critic verify-resolutions` mode + stop-hook gate awareness

<!-- prawduct: chunks=02 | status=shipped | scope=v1.5 -->

**Why:** v1.5 thread C — the "Critic flagged 1-2 BLOCKING findings, builder fixed them, re-review pays full chunk-mode latency to confirm a one-line change" friction motivated this work (backlog entry 2026-05-20). Chunk 01 added the `commit_reviewed` anchor; this chunk lands the mode that uses it.

**What:**

1. **Fourth Critic mode `verify-resolutions`.** Goals 1-3 against the union of (prior `files_reviewed`) ∪ (files changed since prior `commit_reviewed`). Target wall-clock 1-2 min, same as `chunk`. The verbose persisted form is `"verify-resolutions (delta review, prior findings only)"`; bare token rejected by the schema validator.

2. **`_compute_verify_resolutions_scope` helper.** Reads the prior findings file, extracts the anchor, runs `git diff --name-only <commit_reviewed>` + `git ls-files --others --exclude-standard`, filters `_is_metadata_path` from the delta (so incidental `.prawduct/` and other metadata churn doesn't inflate the threshold — symmetric with `_verify_resolutions_gate_check`), applies the widening demotion `len(delta) > 2 * prior + 5`, and returns the scope union. Fail-closed for missing findings, missing/unresolvable `commit_reviewed`, no actionable findings, or scope-widening — every demotion category returns `(empty_list, categorized_reason)` so callers fall through to `/critic chunk` or `/critic final`.

3. **Stop-hook gate awareness.** A `verify-resolutions` findings file clears the Critic gate only when current chunk diff is a subset of the findings' `files_reviewed` (`_verify_resolutions_gate_check`). Out-of-scope chunk diff produces a specific BLOCKER message naming the out-of-scope files. Other modes (chunk/final/cumulative) bypass the subcheck — the standard gate logic applies.

4. **End-of-cycle advisory extended.** `_critic_session_satisfies_gate` now treats both `_CRITIC_MODE_CHUNK` and `_CRITIC_MODE_VERIFY_RESOLUTIONS` as partial-coverage modes (`_CRITIC_MODE_GOALS_1_3_ONLY`). Closing a plan with verify-resolutions fires the same WARNING as closing with chunk — Goals 4-7 + Learnings Cross-Check + Backlog Reconciliation still need a `/critic final`.

5. **Docs propagated across all four Critic surfaces.** `agents/critic/SKILL.md` Modes section (one line, ≤2918 tokens — well under the 3050 budget), `agents/critic/review-cycle.md` per-mode table (new column + new "Verify-resolutions scope and demotion" subsection with demotion-criteria table), `templates/critic-review.md` (full mode bullet with scope/demotion/gate behavior), `.prawduct/critic-review.md` (sync-propagated; manifest hash refreshed), `.claude/skills/critic/SKILL.md` (argument-hint + step 1 expansion).

**Dogfood validation:** Chunk-mode Critic surfaced 2 WARNINGs (advisory-gate gap + metadata-filtering gap) and 1 NOTE (defense-in-depth, deferred to Chunk 03 per the NOTE's own recommendation). After fixing both warnings, `/critic verify-resolutions` against the same chunk completed in single-pass against the 7-file scope and confirmed both resolutions with 0 findings — the user-feedback motivation ("re-review at full latency for a one-line fix") empirically resolved on first use. First framework-side proof the mode delivers its claimed proportionality.

**Test coverage:** 1316 passing (+21 over Chunk 01's 1295). New `TestVerifyResolutionsMode` class (20 tests) covers: validator accepts verbose form / rejects bare token, helper fail-safe modes (missing findings, unreadable JSON, missing `commit_reviewed`, no actionable findings, NOTE-only findings, unresolved commit, scope widening at threshold boundary, metadata filtering), gate-check (other modes bypass, in-scope passes, out-of-scope rejects with named file, metadata-path session changes ignored, fail-closed on unreadable findings), and end-to-end stop-hook integration (in-scope accept, out-of-scope reject with specific BLOCKER message). Extended `TestCriticModeGate` with the verify-resolutions advisory case and a cumulative-satisfies case.

**Backlog:** N1 (expose `_compute_verify_resolutions_scope` as a CLI subcommand so the Critic agent's invocation path also enforces the widening threshold — currently the agent reimplements it from the SKILL.md prose) deferred to Chunk 03 per the NOTE's own recommendation.

## 2026-05-19: `/pr` doc-only fast-path

<!-- prawduct: release=v1.4.0 | status=shipped | scope=v1.4 -->

**Why:** Pain-point audit (this session) found `/pr create` runs the full cumulative-Critic + PR-reviewer gates even when the entire `merge-base...HEAD` diff is `.md` — a one-line `.prawduct/backlog.md` edit on a protected branch was a 10-minute ordeal. The stop hook already exempts session-end doc-only changes (`_session_changes_are_doc_only`), but `/pr` did not inherit that proportionality. Audit verdicts captured the gap; this entry closes it for the create flow.

**What:** New `check-pr-doc-only` product-hook subcommand mirrors the stop hook's exemption at the PR boundary, computing the diff over `merge-base...HEAD` (not the session baseline — semantically required because a PR can span multiple sessions). Base resolution uses the same `origin/main` → `main` → `HEAD~1` precedence as `_coverage_resolve_base`, so the gate sees the same diff surface as the cumulative-Critic flow. `.claude/skills/pr/SKILL.md` gains a Step 1b that calls the new subcommand; exit 0 skips Steps 2 (cumulative-Critic), 2b (operator-verification), 3 (PR reviewer), and 4 (review evidence gate), jumping straight to Step 5 (Create PR). Exit 1 (any reason — non-`.md` file present, empty diff, no resolvable base, git failure) falls through to the full review path. The gate fails closed by design.

**Scope deferred:** The other three pain points surfaced in the audit are not addressed here. (1) Small-bugfix proportionality (no code-change escape hatch) — open. (2) Many-small-chunks Critic overhead — partially mitigated via wave-batching + chunk-mode already; no further work. (3) develop→main artifact stripping — backlog item filed 2026-05-19, not implemented. The doc-only fast-path was the cheapest win and the most acute friction.

**Test coverage:** 1284 passing (+6 over Chunk 14's 1278). `TestCheckPrDocOnlySubcommand` (6 tests) covers: all-`.md` exits 0; mixed `.md`+code exits 1 with the offending path in stderr; code-only exits 1; `.yaml` in `.prawduct/` (governance file, not docs) exits 1; empty diff exits 1 (fail-closed: no diff ≠ doc-only); no resolvable base exits 1 (fail-closed: cannot evaluate). Tests use a real git repo per the `_init_real_git_repo` pattern — the subcommand calls real `git diff`, mocking it would just re-test the mock.

**Version:** v1.4.0 (was 1.3.17). Joins the v1.4 release alongside the F10 operator-verification gate (Chunk 14) and the earlier wave work. The fast-path is the closing piece of v1.4's "PR-boundary proportionality" theme.

## 2026-05-19: Chunk 14 — F10 operator-verification queue + `/pr` BLOCKING gate

<!-- prawduct: chunks=05,06,07,08,09,10,11,12,13,14 | release=v1.4.0 | status=shipped | scope=v1.4 -->

**Why:** Final v1.4 chunk. Visual / live-integration changes have always shipped with ad-hoc "user-side smoke test recommended" caveats — no tracking, no enforcement, no work-log of why a change merged before its human verification was complete. F10 closes the gap: an append-only queue (`.prawduct/operator-verification.md`), a `/pr create` BLOCKING gate when `operator_verification_required: true`, an explicit override (`/pr create --accept-pending-verification "rationale"`) that records the bypass into the queue file itself (the queue *is* the work-log), and a deliberate user-action drain (`prawduct-setup verify <dir> <VRF-id>`). Per the Chunk 10 learning *Auto-enable belongs with visibility, not enforcement*, the gate ships **off by default** in v1.4.0 — explicit opt-in via `migrate --enable-operator-verification` (deviating from the maintenance-plan's "default true" because BLOCKING enforcement must be a workflow commitment users see before it bites). The migration runner is the third entry in the Wave-3 per-feature opt-in trio (coverage, settings-layout, operator-verification).

**What:** Six surfaces — new lib module, new product-hook commands, new prawduct-setup subcommand + migrate flag, new template, new `/pr` skill step, Critic Goal 2 + methodology + build-plan-template hooks.

1. **`tools/lib/operator_verification.py`.** New ~330-line module. Parser: scans for `## VRF-<id>` headings, captures first non-blank body line as `**Status:** pending|verified|accepted`. Missing/unknown status defaults to `pending` (the "Escape hatches in classification create silent failures" learning — unknown is the blocking branch). Mutators (`mark_verified`, `mark_accepted`) preserve every body line outside the status, append `**Verified:** YYYY-MM-DD` or `**Accepted:** YYYY-MM-DD — rationale: <text>`, and refuse the wrong direction (verifying an `accepted` entry would erase the override rationale — raises ValueError). Runners (`run_check_operator_verification`, `run_verify_entry`, `run_accept_pending`) return the standard `{product_dir, ..., actions, notes}` dict shape used by other prawduct-setup runners. Column-0 YAML scanner (`is_operator_verification_required`) mirrors the F4/F5 inline-comment-tolerant pattern.

2. **`tools/product-hook` — `check-operator-verification` and `accept-operator-verification "<rationale>"` subcommands.** `check` mirrors `check-cumulative-critic` semantics: exit 0 when the gate is satisfied (flag off OR no pending entries); exit 1 with stderr message naming the first pending VRF-id and suggesting next steps when blocked. `accept` flips every pending entry to accepted with the rationale recorded into each entry (the override is per-PR; future PRs reblock if new pending entries appear). Missing or whitespace-only rationale rejected — the rationale is the work-log entry, refusing it would leave a silent override trail.

3. **`tools/lib/migrate_cmd.py::enable_v1_4_operator_verification` + `run_migrate_operator_verification`.** Modeled on `enable_v1_4_coverage`, NOT `enable_v1_4_settings_layout`: flips `operator_verification_required: false → true` in project-state.yaml (or appends a documented block when key absent), places the queue template from `templates/operator-verification.md` if absent (queue file must exist before the gate can read it), sets `manifest['v1_4_operator_verification_enabled'] = True` for one-shot tracking. `force=True` bypasses the one-shot check. Existing queue file content is NEVER overwritten (place-once-style — user-authored append history is sacred).

4. **`tools/prawduct-setup.py`.** New `--enable-operator-verification` migrate flag added to the existing per-feature-opt-in CLI (extends the feature-flag list from Chunk 12). New `verify` subcommand: `prawduct-setup verify <product_dir> <VRF-id> [--json]` — drains a single pending entry. Refuses to verify an `accepted` entry with an actionable error message.

5. **`templates/operator-verification.md`.** New queue template (placed by migration, not init). Documents the schema, the gate behavior, the drain UX, and the override semantics in an HTML comment. Format-by-example below the comment.

6. **`.claude/skills/pr/SKILL.md` — Step 2b: Operator-verification gate.** New mandatory step inserted between cumulative-Critic gate (Step 2) and Independent reviewer (Step 3). Detects `--accept-pending-verification "rationale"` in `$ARGUMENTS`; runs `check-operator-verification`; on exit 1, either invokes `accept-operator-verification "<rationale>"` (override path) or blocks with the two-option message (verify-each path). Allowed-tools updated for both new product-hook subcommands.

7. **Critic Goal 2 + methodology + build-plan template hooks.** `agents/critic/SKILL.md` and `templates/critic-review.md` Goal 2 each gain a one-line NOTE check: when `operator_verification_required: true` AND chunk declares `Visual change: yes`, queue must reference the chunk → NOTE. `methodology/building.md` chunk-close step gains a 2-sentence Operator-verification pointer (~30 tokens after aggressive trimming + a +25 token budget bump to 4400 with a justifying comment; the maintenance plan's pipeline-coverage requirement is the load-bearing constraint). `templates/build-plan.md` gains an optional `**Visual change:** yes` field, peer to `**Type:**` and `**Foreign API:**`. `templates/project-state.yaml` and `.prawduct/project-state.yaml` each gain the documented `operator_verification_required: false` block. `.claude/skills/prawduct-doctor/SKILL.md` gains a Verify Flow section and `--enable-operator-verification` Migrate Flow subsection.

**Framework default: gate disabled.** The framework's own `.prawduct/project-state.yaml` ships `operator_verification_required: false` — the framework is a CLI/developer-tool with no human-facing UI surface to verify pre-merge. Product repos that ship visual changes opt in via `migrate --enable-operator-verification` after evaluating the workflow consequence.

**Compat:** Strictly additive. Existing repos keep working unchanged — the gate is opt-in, the template field is optional, the Critic NOTE only fires when both the flag is on AND the chunk declares `Visual change: yes`. No sync changes (the queue is placed by the migration, not init). No deprecation pressure: shim removal trigger (per maintenance plan R2) "F10 removes when all known products that ship visual changes run `migrate --enable-operator-verification`" — currently none, since this is v1.4.0 release day.

**Test coverage:** 1278 passing (+54 over Chunk 13's 1224). New `tests/test_operator_verification.py` (54 tests across 11 classes). `TestParseOperatorVerification` (8 tests) covers segmentation: empty/preamble-only, single/multiple entries, unrelated `## Heading` treated as preamble (the parser is lenient on non-VRF headings), missing-Status defaults to pending (silent-failure guard), unknown-status defaults to pending (same), round-trip preserves body verbatim. `TestMarkVerified` (3 tests) covers pending→verified flip, already-verified no-op, accepted→verify refuses with raise. `TestMarkAccepted` (5 tests) covers pending→accepted with rationale, empty / whitespace-only rationale rejected, already-accepted no-op, already-verified no-op (drained states are sacrosanct). `TestPendingHelpers` (1 test) covers count_pending + pending_entries. `TestIsOperatorVerificationRequired` (6 tests) covers the column-0 YAML scanner: missing file/key, true/false values, indented occurrence ignored, **inline-comment tolerance** (Chunk 10 detector/mutator asymmetry lesson reapplied). `TestRunCheckOperatorVerification` (6 tests) covers all return shapes: gate off → satisfied; gate on + no queue file → satisfied (with explanatory message); gate on + empty queue → satisfied; gate on + 1 pending → blocking with first_pending; gate on + 2 pending → pluralized message; drained entries (verified+accepted) don't block. `TestRunVerifyEntry` (5 tests) covers no-`.prawduct/`-dir error, no-queue-file error, unknown-ID error (with known-ID listing), pending→verified (file written back), already-verified no-op, accepted-refused. `TestRunAcceptPending` (3 tests) covers empty-rationale rejection, no-pending clean return, multi-entry flip (only pending entries touched). `TestEnableV1_4OperatorVerification` (7 tests) covers the migration policy: one-shot short-circuit, flip existing-false key, append block when key absent, place queue from template if absent, existing queue NEVER overwritten (user append-history sacrosanct), already-on no-op, inline-comment tolerated. `TestRunMigrateOperatorVerification` (4 tests) covers the runner: no-`.prawduct/` error, missing-manifest error, happy-path persists manifest, result shape stable. `TestProductHookCommands` (3 subprocess tests) and `TestPrawductSetupCLI` (2 subprocess tests) verify CLI/hook dispatch wiring — kept intentionally minimal after the first pass tripped pre-existing parallel-xdist resource contention (`TestMatchHistoricalRender::test_depth_cap_respected` flake; backlog updated).

**Dogfooding:** The framework itself ships with the gate **off** (`operator_verification_required: false`) — Prawduct has no human-facing UI surface to verify pre-merge, and turning the gate on during this chunk would be circular (Chunk 14 would need to declare itself a visual change and enqueue an entry, but its delivery is governance plumbing, not a visual change). Migration tested against synthetic fixtures (`TestRunMigrateOperatorVerification`) demonstrates: missing-key path appends a documented block; existing false-key flip preserves inline comments; manifest one-shot tracks "we ran the migration" while project-state ground truth is re-read on each report. The queue template is placed by the migration when absent and untouched when present (user-edit preservation verified by `test_existing_queue_not_overwritten`).

**Token budgets:** `methodology/building.md` bumped 4375 → 4400 (justified inline at the test comment; +25 for the chunk-close pointer, trimmed to ~30 tokens from an initial ~125 before bumping). `agents/critic/SKILL.md` held at 3324 / 3325 (Goal 2 bullet condensed to a single line; no budget bump). `templates/critic-review.md` and `templates/build-plan.md` are not under separate token budgets.

**Wave 3 complete.** v1.4 build plan: 15 chunks shipped (Chunk 00 + Wave 1 (01-04) + Wave 2 (05-10) + Wave 3 (11-14)). The cumulative-Critic + PR gates ride along — Chunk 14 is itself the trigger for the v1.4.0 release PR.

## 2026-05-19: Chunk 13 — F9 learnings lifecycle sentinel tracker

<!-- prawduct: chunks=13 | status=shipped | scope=v1.4 -->

**Why:** Learnings accumulate in `.prawduct/learnings.md` faster than they retire. By the time a rule's failure mode is structurally enforced by a test, the rule itself is still consuming active-rules attention; the file grows until grep-for-relevance stops working. F9 closes the lifecycle gap with three signals (confirmations, created, sentinel) that let the audit identify candidates for promotion (advisory), retirement (sentinel-pass entries moved to historical detail), and stale flags (>90 days, single-confirmation entries). The point isn't to automate retirement — it's to surface what's mechanically eligible so the user makes deliberate keep-or-retire calls instead of letting the file drift.

**What:** Three surfaces — new audit module, CLI subcommand, doctor-skill flow.

1. **`tools/lib/audit_learnings_cmd.py::audit_learnings(product_dir, *, apply, today, run_sentinels) -> dict`.** New ~250-line module. Schema is a single-line HTML comment placed immediately after each `## Title`: `<!-- prawduct-learning: confirmations=N; created=YYYY-MM-DD; sentinel=path::test -->`. All three fields optional — absence means "active, no lifecycle metadata" and the entry is left alone in every audit run. Parser enforces strict placement (metadata must be on the first non-blank body line) so entries that quote example metadata in their prose don't hijack their own classification. Unknown keys are preserved harmlessly for forward compat; malformed pairs (no `=`) are dropped silently to tolerate manual-edit slips. Promotion is advisory only (no file mutation regardless of `apply`) because `learnings.md` doesn't have a sectioned active/promoted split — the count surfaces in the report. Retirement is the only mutation: when `apply=True` AND the sentinel passes, the entry is removed from `learnings.md` and appended to `learnings-detail.md` under a "Historical (structurally enforced)" section (created if absent). Failing sentinels surface in both `retirements` (with `passed=False`, `applied=False`) and `errors` (so users see "fix me" without scanning every retirement record). The `today` and `run_sentinels` parameters are test seams — production uses real wall clock and runs `python3 -m pytest <sentinel> -q` as subprocess; tests can short-circuit via `run_sentinels=False` for hermetic coverage.

2. **`tools/lib/audit_learnings_cmd.py::run_audit_learnings(product_dir, *, apply=False) -> dict`.** Runner shaped like the other `run_*` commands (init/sync/validate/views/migrate_*). Returns `{"error": "..."}` only for structural problems (no `.prawduct/` directory) — a missing `learnings.md` is a clean empty result, not an error. Sentinel subprocess failures are absorbed into per-entry `errors` entries; the runner itself never raises. The module's filename uses the `_cmd.py` convention (mirroring `migrate_cmd.py`, `sync_cmd.py`, etc.) to avoid the function-vs-submodule shadowing trap when `lib/__init__.py` re-exports both.

3. **`tools/prawduct-setup.py audit-learnings` CLI.** New subparser peer to `migrate` and `validate`. Default dry-run reports per-list summaries with status markers (`pending --apply` / `sentinel FAIL` / etc.); `--apply` performs retirement mutations; `--json` emits the stable result dict for downstream tooling. The human-mode output uses `log()` → stderr (matching other prawduct-setup subcommands), JSON mode writes to stdout. Exit 0 on success including empty results; exit 1 only on structural errors so shell-pipeline callers can branch reliably.

4. **`.claude/skills/prawduct-doctor/SKILL.md` — new Audit Learnings Flow.** Routing table grew a fourth flow next to Onboard / Health / Migrate. Trigger phrases ("audit learnings", "retire structurally-enforced learnings", "check lifecycle metadata") and the `--apply` consequence are spelled out. The skill body explains the schema with a concrete example so users don't need to read the module docstring to annotate their first entry.

**Compat:** Strictly additive. Existing `learnings.md` files keep working unchanged — entries without the metadata comment are treated as "active, no lifecycle metadata" and never appear in any audit list. No sync changes; the audit is user-invoked only. `learnings-detail.md` is created only when `--apply` retires at least one entry; the historical section header is created idempotently (running again finds it and appends rather than duplicating). The `LearningEntry` dataclass + parser are new public surface (re-exported from `lib/__init__.py`) but nothing depends on them yet.

**Test coverage:** 1224 passing (+40 over Chunk 12's 1184). New `tests/test_audit_learnings.py` (40 tests across 6 test classes). `TestParseLearningMetadata` (8 tests) covers the single-line parser: well-formed all-fields, absent comment returns None, partial metadata, whitespace tolerance, trailing semicolons, unknown keys preserved (forward compat), non-prawduct comments ignored, malformed pairs dropped. `TestParseLearningsFile` (6 tests) covers segmentation: empty file, preamble-only, single entry with and without metadata, mixed annotated/unannotated entries, strict placement rule (metadata must be first non-blank body line), round-trip preserves body verbatim. `TestAuditLearnings` (13 tests) covers classification: empty file no-op, promotion candidate surfaces at confirmations≥2, single confirmation not promoted, stale flag at >90 days + confirmations≤1, recent entry not stale, confirmed entry not stale even when old, malformed-date error, malformed-confirmations error, sentinel skip when `run_sentinels=False`, `apply=False` doesn't mutate, `apply=True` with passing sentinel moves entry (uses monkeypatch on the module's `run_sentinel`), `apply=True` appends to existing detail without duplicating the historical header, failing sentinel surfaces as error AND keeps entry in learnings.md, unannotated entries untouched, result shape stable. `TestRunAuditLearnings` (3 tests) covers the runner: no `.prawduct/` returns error, missing `learnings.md` returns clean empty, result shape stable on success. `TestRunSentinel` (3 tests) exercises the real subprocess path against synthetic passing/failing/nonexistent tests in a tmp_path — pins the contract that the subprocess wrapper does NOT raise on common failure modes. `TestAuditLearningsCLI` (3 tests) covers the dispatch wiring: JSON output keys are stable, human mode emits to stderr (Critic NOTE-equivalent: callers that filter for JSON on stdout aren't confused by status text), no-prawduct exits 1.

**Dogfooding:** Annotated two existing entries in `.prawduct/learnings.md` to verify the schema round-trips and the audit classifies correctly. Entry "Coherence cascades require checking summaries" got `<!-- prawduct-learning: confirmations=2; created=2026-01-30 -->` reflecting the "Reinforced 2026-02-22 with identical miss" note in its body — surfaces as a promotion candidate. Entry "Framework ownership follows the write strategy" got `confirmations=1; created=2026-05-19; sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip` — the sentinel test was added in Chunk 11 specifically as a regression for the failure mode this learning warns about, making it the canonical structurally-enforced check. `prawduct-setup.py audit-learnings .` returns the entry as a retirement candidate (sentinel passes); JSON mode emits the stable shape with `applied: false`. Did NOT run `--apply` against the live framework — the learning is too recent (Chunk 11) to retire, and the unit tests cover the apply path against synthetic fixtures. The dogfood demonstrates the audit correctly identifies the candidate; whether to retire is a deliberate later decision.

## 2026-05-19: Chunk 12 — F5b settings-layout migration command + product-repo dry-run

<!-- prawduct: chunks=12 | status=shipped | scope=v1.4 -->

**Why:** Wave 3 closes F5 with the user-facing opt-in pair to F5a's silent auto-commit. F5a quarantines framework-managed drift to single `chore(sync):` markers on every sync; F5b stamps the product as explicitly on the canonical minimal settings.json layout so v1.4.1's planned Critic NOTE on un-stamped repos has a single state bit to read. The chunk is mostly a *signal* operation: for products that have been syncing regularly (the framework template's hook block has been at the canonical minimal shape — single-line `python3 product-hook <event>` dispatches — since v1.3.x), the migration is a no-op file-wise. For older repos with v1/v3 hook markers (`framework-path`, `governance-hook`, `prawduct-statusline`) that normal sync skipped, the migration runs an aggressive `legacy_cleanup=True` pass and strips them. The manifest flag is the contract; the file mutation is the side-effect when applicable.

**What:** Three surfaces — migration policy in lib, runner with framework resolution, CLI dispatch flag + skill flow.

1. **`tools/lib/migrate_cmd.py::enable_v1_4_settings_layout(product_dir, template_path, subs, manifest, *, force=False) -> (actions, notes)`.** Pure policy function: refuses to run when manifest already carries `v1_4_settings_migrated: True` (without `force`); reads `.claude/settings.json` and short-circuits cleanly if absent (returns empty without setting the flag — the flag means "I migrated," not "I tried and found nothing"); parse-validates the JSON before mutation so an unparseable settings.json surfaces a diagnostic NOTE and refuses to flip the flag (silent advertising of a never-actually-ran migration is the failure mode this guards against); invokes `merge_settings(..., legacy_cleanup=True)`; reports either "Normalized..." (file changed) or "already on the canonical minimal layout" (no-op) so users can tell the migration succeeded vs. silently failed. Always appends the v1.4.1-NOTE-quieting note as the load-bearing user-facing signal. Manifest flag is set *after* the cleanup pass succeeds, never before — guards against parse-failure paths advertising completion.

2. **`tools/lib/migrate_cmd.py::run_migrate_settings_layout(product_dir, *, force=False) -> dict`.** User-facing runner mirroring `run_migrate_coverage` shape: loads sync-manifest.json, resolves framework via the same `_resolve_framework_dir(manifest, None, product_path)` call sync uses (so error wording — "set `PRAWDUCT_FRAMEWORK_DIR` or clone the framework as a sibling" — is identical across commands), constructs `{{PRODUCT_NAME}}` / `{{PRAWDUCT_VERSION}}` subs from `infer_product_name(product_dir)` ∪ manifest cache ∪ directory name fallback (the same priority chain `run_sync` uses, picked up via `infer_product_name` from core), invokes the policy function, persists manifest. Result shape: `{product_dir, migrated, force, actions, notes}` (or `{error}`) — fixed keys so JSON-mode callers don't branch.

3. **`tools/prawduct-setup.py migrate` CLI.** New `--enable-settings-layout` flag on the existing `migrate` subparser. Dispatch is now a feature-flag list — exactly one flag must be set; both flags rejected with explicit "Run them as separate commands" error rather than auto-chained, because two migrations in one invocation would mask interleaved failure modes. Success-label, on/off-field, and on/off-label are parameterized per active flag so the human-output formatting (`{label}: no changes ({path})\n  v1_4_settings_migrated is ON in manifest.`) generalizes for the F10 operator-verification flag the maintenance plan reserves a slot for. `--force` documentation expanded to cover both use cases (re-surface coverage NOTEs after wiring a verifier, re-normalize hand-edited settings).

**`.claude/skills/prawduct-doctor/SKILL.md` — Migrate Flow.** Split the prior single-flag section into two subsections (`--enable-coverage` and `--enable-settings-layout`), each naming its trigger phrases ("turn on F4", "stamp settings layout", "run migrate-settings"), the workflow consequence (BLOCKING vs. NOTE-quieting), and the user-confirmation step. Dropped a single shared `--force` paragraph at the end so the flag's two use cases are spelled out (coverage: re-surface evidence NOTEs after wiring a verifier; settings: re-normalize after hand-edit).

**Test coverage:** 1184 passing (+15 over Chunk 11's 1169). New `TestEnableV1_4SettingsLayout` (8 tests) covers the policy function: missing settings.json no-op (no flag set); already-minimal sets flag only with explanatory NOTE; legacy v1 markers stripped with `governance-hook` regression assertion; user-authored Stop hook preserved alongside prawduct hook through legacy cleanup; non-prawduct top-level keys (customSetting, permissions) preserved verbatim; manifest one-shot short-circuits without `force`; `force=True` bypasses one-shot; bad JSON → diagnostic NOTE without flag flip (the silent-success failure mode). New `TestRunMigrateSettingsLayout` (7 tests) covers the runner: no `.prawduct/` returns error; missing manifest returns error naming `prawduct-setup setup` as next step; framework_source pointing nowhere returns actionable error; manifest flag persisted after successful run; second invocation without `--force` short-circuits even when settings.json has been hand-mutated to a bad shape; `--force` re-runs and re-normalizes; result shape is stable across all branches (keys `product_dir`, `migrated`, `force`, `actions`, `notes` always present). All tests use real-filesystem `tmp_path` fixtures with synthetic framework checkouts; no subprocess mocking.

**Dogfooding:** Synthetic dry-run against `discodon` and `hallucinote` in ephemeral `/tmp/migrate_settings_dryrun/` clones (no commits to source repos). **Discodon** (last synced at v1.3.16): exactly one file change — `companyAnnouncements` banner version-bumped to v1.3.17 (framework-managed banner is always-update by design). Hooks unchanged; the layout was already minimal. **Hallucinote** (synced at v1.3.17): true no-op; settings.json byte-identical before and after, `actions == []`, single NOTE "already on the canonical minimal layout." Both produced `v1_4_settings_migrated: True` in their sync-manifest.json. Second-run without `--force` is a fast short-circuit (no actions, no notes); second-run with `--force` re-walks the cleanup pass and produces the same already-minimal NOTE — confirms idempotence. JSON output (`--json --force`) emits the stable result shape verbatim. Pattern confirms F5b's intent: most active products see only a flag flip; the legacy_cleanup pass is the safety net for stale repos.

**Compat:** Strictly additive. The migration is opt-in (no auto-flip from sync), one-shot per product (manifest flag), and idempotent without `--force`. Existing settings.json files keep working unchanged on every sync — `merge_settings(..., legacy_cleanup=False)` continues to be the sync-path call, so products that never run the migration see no behavior change in v1.4.0. Critic NOTE on un-stamped products is reserved for v1.4.1 (`maintenance-plan.md` F5 Compat line), not this chunk — Chunk 12 ships only the user-facing path. Shim removal trigger (per maintenance plan): "F5 removes when all known products run `migrate-settings`."

## 2026-05-19: Chunk 11 — F5a sync auto-commit + protected-branch preconditions

<!-- prawduct: chunks=11 | status=shipped | scope=v1.4 -->

**Why:** Every framework upgrade left product repos with framework-managed drift co-mingled in unrelated chunk commits — three downstream repos showed banner-rename + product-hook drift mixed with chunk diffs every release, generating Critic NOTEs that the chunk owner had no business addressing. F5a quarantines framework drift to one dated marker commit per upgrade so chunk diffs stop carrying upstream churn. The chunk also lands the precondition-gated safety surface that lets the auto-commit ship default-on without surprising users: WIP, protected branches, and in-progress git ops each block the commit and surface a marker the next session sees.

**What:** Five surfaces — sync-side auto-commit, precondition gates, project-state config block, session marker, and briefing surfacing.

1. **`tools/lib/sync_cmd.py::_try_auto_commit(product, *, actions, notes, manifest)`.** New ~150-line helper called at the tail of `run_sync()`, after all file mutations and the manifest write. Reads `git status --porcelain -z`, partitions changes via `_framework_known_paths(manifest)` (manifest `files` ∪ `{.prawduct/sync-manifest.json, .prawduct/project-state.yaml, .gitignore}`), and if all changes are framework-known + preconditions pass, stages just those paths and runs `git commit -m "chore(sync): prawduct vX.Y.Z"`. `PLACE_ONCE_TEMPLATES` / `PLACE_ONCE_COPY` are *deliberately excluded* from the framework-known set (Critic chunk-mode finding 1): place-once files (`.prawduct/change-log.md`, `.prawduct/backlog.md`, `tests/conftest.py`) are user-authored after creation, and including them would have swept user chunk-close appends into the very `chore(sync):` commits F5a aims to prevent. Trade-off: a freshly created place-once file leaves an untracked file in the working tree for the user to commit deliberately, which is appropriate for first-time initialization moments. Contract is best-effort: any subprocess failure or unexpected state degrades to "skip auto-commit, leave drift in working tree" — sync itself must never fail because of this step.

2. **Preconditions (each a single helper, each independently testable).** `_current_branch` (returns empty on detached HEAD, treated as protected to avoid unreachable commits); `_git_op_in_progress` (checks `MERGE_HEAD`, `REBASE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, plus `rebase-merge/` and `rebase-apply/` directories for interactive rebase); `_branch_is_protected` (fnmatch globs, so `release/*` works without regex weight); the WIP check falls out of the `_classify_changes` partition — any porcelain entry not in the framework-known set is user WIP and blocks the commit.

3. **`.prawduct/project-state.yaml` `sync:` block.** New optional section parsed by `_read_sync_config` (column-0 YAML scanner mirroring `views.py::is_views_enabled` and the Chunk 09/10 `_read_bool_yaml_key` pattern — no PyYAML dependency, inline-comment tolerant after Chunk 10's asymmetry lesson). Defaults: `auto_commit: true`, `protected_branches: [main, master, "release/*"]`. Empty `protected_branches:` (no list entries) falls back to defaults rather than meaning "no protection" — likelier to be a YAML mistake than an intentional opt-out; `protected_branches: []` is the explicit empty form. Templates and the framework's own state file ship unchanged for v1.4 — the block is read with defaults when absent, so existing products auto-get F5a behavior on next sync without a migration step (the Chunk 12 migrate-settings shim handles the settings.json half).

4. **`.prawduct/.sync-pending` marker (gitignored).** Written when preconditions block; JSON shape `{reason, blocked_by, version, ts}`. Added to `tools/lib/core.py::GITIGNORE_ENTRIES`, the framework's own `.gitignore`, and `tools/product-hook::_SESSION_GITIGNORED_PATHS` (the three-way mirror has a coverage-gap test that catches drift — caught and fixed during chunk implementation). Cleared on successful auto-commit so stale markers don't lie about pending state.

5. **`tools/product-hook::assemble_session_briefing` surfacing.** Reads `.sync-pending` when present and emits a one-line `Framework sync pending (vX.Y.Z): <reason>` block. Corrupt JSON degrades to a "marker present but unreadable" pointer rather than crashing the briefing — `briefing must never block session start` is the load-bearing invariant the existing prawduct:ok-broad-except markers enforce on this path.

**Settings.json minimization (the other half of F5a's title):** No-op deliberately. The maintenance plan's F5 Critic note had foreseen this: "the 'settings.json minimization' half is mostly cosmetic in current product repos — hook bodies are already one-line `python3 tools/product-hook ...` dispatches." Inspecting `templates/product-settings.json` confirmed the prediction — `SessionStart` and `Stop` are already single-line command dispatches; the schema fields (`type`, `command`, `statusMessage`, `matcher`) are required by Claude Code's hook config, not framework cruft. Documenting the no-op here so the next reader doesn't grep for missing work.

**Compat:** Strictly additive on the framework side; safe-by-default on the product side. Existing repos that never ran the migration still pass the porcelain partition (managed paths derived from the *manifest* files list, which sync keeps current). The default `protected_branches` covers `main`/`master`/`release/*` — for the framework itself (always on `main`), auto-commit never fires; drift stays in the working tree for deliberate commit. Products typically work on `feature/...` branches and see auto-commit as the happy path. No deprecation pressure on existing settings.json layouts — Chunk 12 ships the migrate-settings command for the explicit opt-in.

**Test coverage:** 1169 passing (+26 over Chunk 10's 1143). New `TestReadSyncConfig` (6 tests) covers the YAML scanner: defaults when project-state absent / no sync block; explicit disable; custom protected branches; **inline-comment tolerance on the value line** (mirrors the Chunk 10 detector/mutator asymmetry fix — the lesson stuck, the test names it explicitly); malformed YAML falls back to defaults. `TestBranchIsProtected` (3 tests) covers exact match, glob match, detached-HEAD-treated-as-protected. `TestAutoCommitHappyPath` (4 tests) covers single-commit creation, marker clearing on success, clean working tree after commit, version-pinned message. `TestAutoCommitPreconditions` (6 tests) covers each precondition independently — protected branch, WIP, rebase-merge, MERGE_HEAD, CHERRY_PICK_HEAD, explicit auto_commit=false (no marker because disable is a choice not a failure). `TestAutoCommitSafety` (4 tests) covers not-a-git-repo silent no-op, stale-marker clearing on no-drift sync, managed-only commit content, plus `test_user_authored_place_once_edits_treated_as_wip` (regression for the in-chunk Critic finding 1: a user append to `.prawduct/change-log.md` must NOT be swept into the chore(sync) commit). `TestSessionBriefing` gains 3 tests: marker surfaces in briefing, absent marker is silent, corrupt-JSON marker degrades to a usable warning. All tests use real-filesystem `tmp_path` fixtures with `git init` — no `subprocess` mocking, matching the test-prawduct-sync style.

**Dogfooding:** `python3 tools/prawduct-setup.py sync .` against the framework itself produces the briefing's `PRAWDUCT SYNC: Framework updated\n  + Refreshed manifest for ...` lines plus a clean `git status` because the framework is on `main` (protected by default) — the safe-path verifying detached-HEAD protection by branch-name. The `.prawduct/.sync-pending` marker file is NOT produced in this case because the framework has no framework-managed drift to commit (only the manifest refresh, which the sync wrote as a refresh action with no porcelain diff). Synthetic dry-run across four scenarios in ephemeral `/tmp/dbg*` repos confirms the happy path: fresh feature-branch sync with framework drift produces one `chore(sync): prawduct vX.Y.Z` commit; subsequent sync with no drift is a clean no-op; planting WIP blocks the commit and writes the marker; protected-branch (`main`) blocks the commit with `"branch 'main' is protected"` in `blocked_by`.

**Critic chunk review:** 0 BLOCKING, 2 WARNINGs, 1 NOTE. (1) WARNING — `_framework_known_paths` included `PLACE_ONCE_TEMPLATES` / `PLACE_ONCE_COPY`, which would sweep user-authored change-log/backlog appends into chore(sync) marker commits (the exact co-mingling F5a aims to prevent). **Fixed in-chunk** by dropping the place-once sources from the partition set and adding `test_user_authored_place_once_edits_treated_as_wip` regression. Docstring updated to explain the deliberate exclusion. (2) WARNING — docstring cited `.prawduct/learnings.md` as a framework-known place-once file but it isn't in any registry (behavior was correct; only the example was wrong). **Fixed in-chunk** by removing the misleading mention. (3) NOTE — `test_managed_paths_committed_wip_excluded` accepts `.gitignore` only because the fixture writes the current `GITIGNORE_ENTRIES`, so `update_gitignore` finds nothing to drift; future chunks adding a gitignore entry will trip the assertion. **Filed to backlog** as a fixture-stability hardening item. The auto-commit happy path + six independent precondition gates + best-effort degraded paths are all covered; F5a's anti-co-mingling intent is now enforced by test, not just docstring.

## 2026-05-19: Chunk 10 — F4c migration tooling + fingerprint terminology cleanup

<!-- prawduct: chunks=10 | status=shipped | scope=v1.4 -->

**Why:** Wave 3 closer. Chunks 08/09 shipped the F4 schema (`verifier`-discriminated coverage fields) and Critic enforcement (`verify-coverage` BLOCKING per missing file). Chunk 10 closes the loop with a user-facing opt-in path so products can move from "schema dogfooded, enforcement off" to "enforcement on" deliberately — not silently on sync (which would surprise downstream products with sudden BLOCKING findings). Also folds in the v1.5-deprecation signaling for legacy evidence shape and a terminology cleanup of "fingerprint" — the tree-hash mechanism that name referred to was removed pre-v1.4, but the word lingered in 5 spots where it was actively misleading.

**What:** Four surfaces — new migration helper, new CLI subcommand, doctor-skill flow, terminology refresh.

1. **`tools/lib/migrate_cmd.py::enable_v1_4_coverage(product_dir, manifest, *, force=False) -> (actions, notes)`.** New ~110-line helper modeled on `enable_v1_4_views` but with three deliberate divergences: (a) returns `(actions, notes)` instead of just actions — the deprecation guidance is a first-class output, not a side channel; (b) NOT auto-called from `run_sync()` — coverage enforcement is a workflow commitment, not a silent upgrade like derived views were; (c) `force=True` parameter re-runs the read-and-NOTE pass for users who want to re-check evidence shape after wiring up a verifier. Mutates `project-state.yaml` (flip `false → true`, or append a documented block when key absent), mutates `manifest['v1_4_coverage_enabled']` (one-shot tracking — accidental re-invocations short-circuit). Inspects `.test-evidence.json` to surface deprecation NOTEs: missing file → "run the verifier first"; legacy shape (no `verifier`) → v1.5-removal warning pointing at `tools/test-reference-verify`; modern shape → no NOTE (don't cry wolf at products already on the new schema).

2. **`tools/lib/migrate_cmd.py::run_migrate_coverage(product_dir, *, force=False) -> dict`.** Thin runner shaped like the other `run_*` commands (init/sync/validate/views) — loads manifest, calls the helper, persists, re-reads on-disk `coverage_required` to report ground truth (the manifest flag tracks "we ran the migration"; the YAML may have been hand-edited between runs). Returns `{product_dir, enabled, force, actions, notes}` for both human and JSON output.

3. **`tools/prawduct-setup.py migrate` subparser.** New `migrate --enable-coverage <product_dir>` subcommand with `--force` and `--json` flags. Missing-feature-flag path exits 1 with usage help — `migrate <dir>` alone is treated as user-uncertainty, not silent success. Per-feature opt-in pattern extends naturally to future flags (e.g. `--enable-operator-verification` for Chunk 14's F10).

4. **`.claude/skills/prawduct-doctor/SKILL.md` — new Migrate Flow.** Doctor skill gains explicit routing for "enable coverage" / "turn on F4" / similar user requests. The flow confirms intent before running (coverage is a workflow commitment, not a doc tweak), surfaces both actions and notes prominently, and points the user at the verifier if legacy-shape evidence is detected.

5. **Terminology cleanup (5 sites).** "Fingerprint" was the old name for a tree-hash freshness mechanism removed pre-v1.4; lingering uses were actively misleading new readers into looking for a hash-based system that doesn't exist. Updated:
   - `tools/test-reference-verify` shebang docs: "fingerprint record produced by pytest" → "pytest-emitted v1.3.x-shape evidence record (the 'legacy' shape — pre-F4a fields)" with note that "fingerprint" was the old name from when freshness relied on tree-hash.
   - `tools/product-hook::tests_are_current` docstring: "No fingerprinting or content hashing" → "No tree-hashing or content fingerprinting (those mechanisms were removed pre-v1.4 after chronic false positives from metadata churn)".
   - `tools/product-hook::_validate_evidence_schema` docstring: "Legacy fingerprint-only evidence" → "Legacy evidence (pre-F4a shape: no `verifier` field — historically called 'fingerprint' though the tree-hash mechanism it referred to was removed pre-v1.4)" with v1.5-removal reference to Chunk 10's migration NOTE.
   - `templates/build-governance.md` + `.prawduct/build-governance.md` (lockstep): same prose updated, plus a bolded **v1.5 removal warning** pointing users at the new migrate subcommand. The line about "Critic enforcement is opt-in" now names the actual command users should run.

**Compat:** Strictly additive. No existing behavior changes — the migration is user-invoked only, never auto-fired from sync. Legacy evidence keeps validating. The manifest gets a new optional key (`v1_4_coverage_enabled`); products that never run migrate just don't have it set.

**Test coverage:** 1143 passing (+17 over Chunk 09's 1126). New `TestEnableV1_4Coverage` (11 tests) covers the helper: missing project-state no-op, pre-v1.4 append, false→true flip, already-on no-rewrite, one-shot manifest short-circuit, `--force` bypasses one-shot, legacy-evidence deprecation note, modern-evidence no-cry-wolf, unparseable-evidence diagnostic, indented-key-doesn't-count-as-top-level, inline-comment-preserved-on-flip (regression for Chunk-10 Critic NOTE on detector/mutator asymmetry). New `TestRunMigrateCoverage` (6 tests) covers the runner: error paths (no .prawduct, no manifest), manifest persistence, ground-truth on-disk reporting, force-flag bypass, stable result shape.

**Dogfooding / synthetic dry-run:** Smoke-tested against four scenarios in `/tmp/mig_test*` repos: (1) fresh enable with no evidence → append block, surface "no evidence" + "next-PR consequence" notes; (2) idempotent re-run → manifest short-circuits, "no changes"; (3) flip `coverage_required: false → true` with legacy evidence + --force → "already-true" note + v1.5-deprecation note; (4) error paths (no .prawduct/, no manifest) → exit 1 with actionable messages. Framework's own `coverage_required` stays `false` — the schema is dogfooded (every chunk's evidence carries F4a fields) but enforcement is held until v1.5 per the maintenance plan's Wave-3 framing. The /tmp dry-runs stand in for real-product (discodon, hallucinote) runs the chunk plan asked for; those follow in their own sessions when product owners opt in.

**Critic chunk review:** 0 BLOCKING, 0 WARNINGs, 3 NOTEs. (1) Detector/mutator asymmetry on inline-commented `coverage_required: false  # comment` → fixed in-chunk with `test_flip_preserves_inline_comment` regression; backlog entry filed for the same pattern in `enable_v1_4_views`. (2) Build-plan stub still named `prawduct-doctor migrate v1.4 --enable-coverage` (pre-unification language from the maintenance plan) → corrected in build-plan.md Description line to `prawduct-setup migrate --enable-coverage` with /prawduct-doctor wrapping; build-plan.md is gitignored, but the change-log entry (this entry) is the canonical record. (3) Product-repo dry-run not captured → addressed by the Dogfooding section above naming the four /tmp scenarios; real-product dry-runs deferred to the products' own sessions.

## 2026-05-19: Chunk 09 — F4b Critic symbol-coverage check + methodology principle

<!-- prawduct: chunks=09 | status=shipped | scope=v1.4 -->

**Why:** Chunk 08 shipped the F4a schema (every chunk now emits `verifier` / `tests_executed` / `changes_referenced` / `coverage_level`) but no enforcement read it. F4b closes the loop: when a project opts in via `coverage_required: true`, the Critic's Goal 1 cross-checks the diff against `changes_referenced` and emits BLOCKING per missing file, with language scaled to the declared `coverage_level` — floor (`referenced`) explicitly disclaims execution; `executed` does not. The chunk's other half is the methodology principle in `building.md` that names what the floor doesn't prove, so authors don't treat "verifier reported clean" as "tests cover this change."

**What:** Three surfaces — new product-hook subcommand, Critic instruction, methodology paragraph.

1. **`tools/product-hook verify-coverage`.** New ~110-line subcommand backed by helpers `_read_bool_yaml_key` (column-0 YAML scanner mirroring `views.py::is_views_enabled`), `_coverage_resolve_base` (matches `tools/test-reference-verify`'s base-resolution so reader and writer agree on diff set), and `_coverage_changed_files` (union of `git diff --name-only BASE` and `git ls-files --others --exclude-standard` — untracked-file inclusion is the silent-failure mode the check exists to catch). Exit semantics: 0 = skipped (`coverage_required: false`, the v1.4 default) or all covered; 1 = preconditions failed (missing/invalid evidence, no `verifier` field, unresolved diff base) or per-file missing coverage. stderr emits one `missing-coverage: PATH (coverage_level: LEVEL) — SUFFIX` line per missing file with `SUFFIX` scaled to level (`floor check — does not prove execution.` vs. `has no executing test.`); the Critic quotes the line verbatim in BLOCKING findings.

2. **Critic Goal 1 (three files in lockstep — `agents/critic/SKILL.md`, `templates/critic-review.md`, `.prawduct/critic-review.md`).** Goal 1 gains one sentence mapping `verify-coverage` exit codes to BLOCKING per file, with explicit instruction not to soften the per-level wording (the wording IS the distinction the chunk introduces). Other exit-1 reasons (missing evidence, no `verifier`, schema invalid) are also BLOCKING — the project opted in, so failing-to-evaluate is real failure, not silent skip.

3. **`methodology/building.md` Test Discipline.** New "Idiomatic tooling, honest coverage" paragraph — language-native incremental/cached runners avoid re-running unchanged tests, the framework asserts the contract (changes covered) not a specific verifier, the reference verifier is a *floor* (catches untested new code, cannot prove execution), and products that need real coverage SHOULD plug in language-native tooling and emit `coverage_level: executed`. This is the F4c methodology principle the maintenance plan called for.

**Compat:** Strictly opt-in. `coverage_required` defaults `false` in v1.4 (set in Chunk 08), so existing projects keep their current Critic behavior — verify-coverage exits 0 with "skipped" and the Critic moves on. Framework dogfoods the schema (every chunk's evidence carries the F4a fields) but doesn't enforce it on itself yet — flag stays off until v1.5 sweep.

**Test coverage:** 1126 passing (+13 over Chunk 08's 1113). New `TestVerifyCoverageSubcommand` in `tests/test_product_hook.py` — 13 tests on real-git mini-repo fixtures (no mocking, matching `test_reference_verifier.py` style since the subcommand's contract is its git interaction): skip-default-false, skip-key-absent, indented-key-doesn't-satisfy-flag, missing-evidence, legacy-evidence-no-verifier, invalid-schema, all-covered-clean, missing-at-referenced-floor-language, missing-at-executed-stronger-language (asserts floor language is NOT emitted at executed level — the per-level distinction is the chunk's reason for existing), multiple-files-listed-individually, untracked-treated-as-missing, no-changes-clean, unresolvable-base-errors. Token-budget tests in `tests/test_v5_methodology.py` bumped: building.md 4275 → 4375 (~75 tokens for the new paragraph after aggressive trimming), SKILL.md 3250 → 3325 (~50 tokens for the Goal-1 bullet — explicitly drawing from the F4 protocol-additions budget the Chunk 00 trim-pass reserved). Both bump-comments instruct future readers to prefer trimming over another bump.

**Dogfooding:** `python3 tools/product-hook verify-coverage` against this chunk's own diff reports `skipped: coverage_required is false (default in v1.4)` — by design (framework holds off until v1.5 to keep template parity with downstream products that need a migration window). The verifier still runs and `.test-evidence.json` carries the F4a fields, so the day enforcement flips on, this chunk is already covered.

**Critic chunk review:** 0 BLOCKING, 0 WARNINGs, 1 NOTE (deferred to backlog — `_read_bool_yaml_key` duplicates the column-0 scanner in `views.py::is_views_enabled`; intentional inline duplication is documented, extraction earns a backlog candidacy when a third caller appears).

## 2026-05-19: Chunk 08 — F4a evidence-schema extension + reference floor verifier

<!-- prawduct: chunks=08 | status=shipped | scope=v1.4 -->

**Why:** Wave 3 opener. The framework's safety claim "tests passed" is currently falsifiable on untested new code — `.test-evidence.json` records pass/fail counts but never asserts that the tests actually *referenced* the code that changed. F4a closes the schema half of this gap: extend the evidence record with four coverage fields (additive, compat-preserving) and ship a reference verifier so products on Python have a working floor implementation. The Critic enforcement that *uses* this data lands in Chunk 09 (F4b); the migration tooling + fingerprint cleanup lands in Chunk 10 (F4c).

**What:** Two surfaces — schema validator + new tool.

1. **Schema extension in `tools/product-hook::_validate_evidence_schema`.** Presence of a `verifier` field is the discriminator. Legacy fingerprint-only evidence (no `verifier`) validates unchanged. When `verifier` IS present, the writer has opted into the coverage schema and `tests_executed` (list), `changes_referenced` (list), and `coverage_level` (enum: `referenced` | `executed`) become conditionally required. Out-of-set `coverage_level` values are rejected with the allowed-set listed. The error precedence (missing > wrong-type > enum) already established for the fingerprint half is preserved.

2. **`tools/test-reference-verify` — floor coverage verifier.** New ~300-line standalone CLI. Resolves a diff base (explicit `--base REV`, else auto-detects `origin/main` → `main` → `HEAD~1`), enumerates changed files (`git diff --name-only BASE` PLUS `git ls-files --others --exclude-standard` so untracked new files participate — the silent-failure mode this exists to catch), extracts Python `def`/`class` symbols via regex (including async-def and shebang-Python scripts without `.py` suffix), greps the test tree for any symbol per changed file, emits the four F4a fields as JSON. Three output modes: stdout (default), `--output PATH` (standalone JSON), `--merge-into PATH` (overlay onto existing fingerprint evidence). Documented in-script as a **floor**, not a default-good-enough — products with non-trivial coverage concerns SHOULD plug in stronger language-native tooling and emit `coverage_level: executed`.

**Template / docs:** `templates/build-governance.md` + `.prawduct/build-governance.md` gain a "Coverage Evidence (v1.4 F4a, opt-in)" section explaining the presence-of-`verifier` discriminator, the enum, the floor caveat, and the `coverage_required` flag (default off). `templates/project-state.yaml` gains a top-level `coverage_required: false` block with comment header; v1.4 default is off because Chunk 09 ships the Critic check that actually enforces it. Framework's own state file mirrors the default.

**Compat:** Strictly additive. Legacy evidence keeps validating with no changes. `coverage_required` default off means existing repos sync the template addition with zero behavior change; opting in is a one-line yaml edit. Schema validator rejects new-shape records that drop a field — a typo like `tests_ran` (vs. `tests_executed`) fails loud instead of silently dropping coverage signal.

**Test coverage:** 1113 passing (+26 over Chunk 07's 1087). New `TestCoverageEvidenceSchema` in `tests/test_product_hook.py` — 7 tests covering: legacy fingerprint-only compat; full coverage evidence accepted; both enum values valid; unknown `coverage_level` rejected with allowed-set listed; `verifier` without companion fields rejected (catches typos); list-type enforcement on `changes_referenced`; empty lists accepted (shape vs. content — content is the Critic's job per Chunk 09). New `tests/test_reference_verifier.py` — 20 tests across 6 classes built on real-git mini-repo fixtures (no mocking): output shape stability, diff-base resolution (explicit / auto / unresolvable), modified-file detection, untracked-file inclusion, untracked-with-test reference matching, unchanged-file exclusion, Python class symbol matching, async-def extraction, shebang-Python script extraction (catches the `tools/foo` CLI-verb pattern), non-Python stem fallback, `--output` writes standalone fields, `--merge-into` preserves fingerprint and overlays F4a, `--output`/`--merge-into` mutual exclusion, missing-file errors, `TestSelfCompat` cross-validates that the verifier's emitted shape satisfies the schema validator (drift catcher).

**Dogfooding:** Verifier run against this chunk's own diff via `python3 tools/test-reference-verify --base HEAD --merge-into .prawduct/.test-evidence.json` produces a `changes_referenced` list of 8 files (all changed files reference some test symbol). `test-status` reports `current`. `validate-evidence` reports `valid` against the merged record.

**Critic chunk review:** 0 BLOCKING, 0 WARNINGs, 3 NOTEs (all resolved in-chunk):

1. Build-plan structure table promised a `templates/project-state.yaml` edit in Chunk 08 — addressed by adding the `coverage_required: false` default now rather than deferring to Chunk 09.
2. `_has_reference` re-opens test files per changed file (O(N*T) I/O) — backlog item filed (`Cache test-file contents in tools/test-reference-verify`).
3. `_extract_symbols` returns empty set when a Python file has no `def`/`class` — docstring updated to flag the floor caveat for next reader.

## 2026-05-19: Chunk 07 — F1c sync auto-enables derived views for existing repos

<!-- prawduct: chunks=07 | status=shipped | scope=v1.4 -->

**Why:** Chunks 05–06 shipped the views pipeline behind `views_enabled: true` with `false` as the template default — products had to opt in via a planned `prawduct-doctor migrate v1.4 --enable-views` migration command. During Chunk 07 planning the user redirected: "all users should get views for free, with no mandatory opt-in. it will be fine." That collapses migration tooling into the sync path (which every existing repo already runs every session) and removes the need for the doctor migration subcommand entirely. The compat shim that matters — untagged legacy entries still render unchanged — already lives in the views.py tag-filtering logic from Chunk 05.

**What:** `tools/lib/migrate_cmd.py::enable_v1_4_views(product_dir, manifest)` — new one-shot helper (~85 lines). Wired into `run_sync()` immediately after `migrate_change_log` / `migrate_backlog`. Behavior:

1. Returns early when `manifest["v1_4_views_enabled"]` is already True (one-shot tracking — first sync flips the flag; subsequent syncs never touch the file, so a user who later sets `views_enabled: false` manually is respected).
2. On `project-state.yaml`, detects the two real-world shapes:
   * **Pre-Chunk-06 v1.3.x bootstrap** (neither key present): appends `scope_rollups: {}` block + `views_enabled: true` block, each with its own comment header matching the new template wording.
   * **Post-Chunk-06 default** (`views_enabled: false` + `scope_rollups: {}` already from template): flips `false` → `true` line-by-line, leaves `scope_rollups: {}` alone.
3. Sets `manifest["v1_4_views_enabled"] = True` regardless of whether the file needed changes — the flag means "this sync has visited the v1.4 migration step," not "we mutated the file." Existing `run_sync` manifest write-back persists it.

**Template changes:** `templates/project-state.yaml` now defaults `views_enabled: true` (was `false`) with updated comment ("enabled by default" → "set to `false` to opt out"). `templates/change-log.md` schema header refreshed to "enabled by default" wording. Framework's own `.prawduct/project-state.yaml` derived-views comment refreshed to match (the value was already `true` for dogfooding).

**Plan revision:** Chunk 07's description in `.prawduct/artifacts/build-plan.md` rewritten — Status line + Context closer + body block. The dropped `prawduct-doctor migrate v1.4 --enable-views` subcommand is captured here, not as deferred work. The maintenance plan F1 compat paragraph + R2 removal-trigger criterion now reflect "auto-enabled, opt-out is explicit." `tools/product-hook cmd_regen_views` docstring updated (Critic NOTE: "opt-in by design" wording was stale).

**Test coverage:** 1087 passing (+10 over Chunk 06 baseline). `TestEnableV1_4Views` in `tests/test_prawduct_sync.py` — 10 tests covering: no project-state no-op; manifest flag short-circuits without reading file; pre-Chunk-06 legacy adds both keys; post-Chunk-06 default flips false→true and preserves scope_rollups; already-on no-edit (flag still records); idempotent second run respects user opt-out; only-scope-missing path; commented-out keys not counted; nested keys not counted (lightweight substring detector intentionally scoped to top level); end-to-end `run_sync` integration confirms manifest flag persists across sessions. `test_every_public_lib_function_referenced_in_some_test` confirms the new function has direct test references.

**Dry-run evidence (discodon + hallucinote):** both repos are v1.3.x bootstraps without either key. Function appends both blocks (~1019 bytes added), sets manifest flag, second pass is byte-identical no-op, and a manual opt-out (setting `false` post-flag) is respected on subsequent passes. Run captured via inline harness against tmp copies — no commits to those repos.

**No regen-views invocation in this chunk** — the F1c work is sync logic only. Each affected repo will see views materialize on the next regen (manual `python3 tools/product-hook regen-views` or chunk-close governance per `methodology/building.md`).

## 2026-05-18: Chunk 06 — F1b remaining views (release-notes + scope-rollups + doctor views)

<!-- prawduct: chunks=06 | status=shipped | scope=v1.4 -->

**Why:** F1a (Chunk 05) shipped the schema, the parser, and one view (build-plan Status). F1's load-bearing premise — *one canonical store, multiple derived views replacing hand-curated summaries* — needs the remaining two views (release notes, scope rollups) before Chunk 07 can ship migration tooling. The doctor `views` subcommand fills the F1 deliverable for ad-hoc inter-commit regen and gives `/prawduct-doctor` users a one-stop dry-run/refresh surface.

**What:** Three views regenerate in one pass via `python3 tools/product-hook regen-views` (or `python3 tools/prawduct-setup.py views <dir> --refresh`):

1. **Status** (existing, from Chunk 05) — build-plan `## Status` checkboxes from `status=shipped` tags.
2. **Release notes** (new) — `.prawduct/release-notes.md` digest, one section per `release=` tag, preserving change-log order (newest first). Multiple change-log entries sharing a release tag merge into one section.
3. **Scope rollups** (new) — `scope_rollups:` top-level block in `project-state.yaml`, listing chunks + releases per `scope=` tag. Alphabetically sorted scopes, deduplicated chunks. Chunk IDs YAML-quoted to preserve leading zeros. Block appended at end-of-file with comment header on first regen; subsequent regens replace the key-and-body in place (preserves surrounding content via `extract_yaml_top_level_block`).

**Shared regen pipeline:** new `views.plan_regen(prawduct_dir) → (enabled, [ViewRegenResult])` + `views.apply_regen(prawduct_dir, results)` helpers consolidate the read/build/write logic so both `product-hook regen-views` and the new doctor `views` subcommand reach the same path. `ViewRegenResult` carries `name` (`status`/`release-notes`/`scope-rollups`), `action` (`noop`/`write`/`create`), `summary`, and the new content — letting the doctor surface dry-run intent without writing.

**Doctor `views` subcommand:** `python3 tools/prawduct-setup.py views <product_dir>` reports per-view freshness (Status / release-notes / scope-rollups) and prompts for `--refresh` when changes would apply. `--refresh` performs the regen. `--json` for scripted consumption. New `tools/lib/views_cmd.py` (~60 lines) wraps `plan_regen` + `apply_regen` with the doctor's payload shape. The /prawduct-doctor skill picks this up via prawduct-setup.py's subparser table.

**Source-of-truth guardrails (broadened from Status to all three views):** Critic Goal 4 ("Derived views" bullet) + templates/critic-review.md + .prawduct/critic-review.md + PR-reviewer SKILL + templates/pr-review.md + .prawduct/pr-review.md + methodology/building.md chunk-close pointer + templates/product-claude.md step 10 all updated. Common message: when `views_enabled: true`, all three views derive from change-log tags via `regen-views`; tag is canonical; any view↔tag mismatch → WARNING ("run regen-views"). Aggressive trim-before-bump kept Critic SKILL.md under the existing 3250 ceiling (broader wording would have grown to 3261; trimmed back to 3243) and templates/product-claude.md block under 3050 (broader wording would have grown to 3061; trimmed back to ≤3050).

**Schema / template changes:** `templates/change-log.md` schema comment expanded to mention the release-notes + scope_rollups outputs (previously only mentioned Status). `templates/project-state.yaml` opt-in comment broadened; `scope_rollups: {}` placeholder added (default empty, populated only on first regen with shipped+scoped entries).

**Test coverage:** 1077 passing (+36 over Chunk 05's 1041). New tests/test_views.py classes: TestExtractYamlTopLevelBlock (6 — find/missing/multi-line/comment-terminated/indented-not-matched/end-of-file), TestBuildScopeView (7 — append/replace/idempotent/empty/multi-sort/non-shipped-excluded/dedup-sort), TestBuildReleaseNotesView (6 — none/in-progress-excluded/single/multi-order/merge/no-release-tag-excluded), TestPlanRegen (4), TestApplyRegen (2), TestRunViewsCommand (3 direct), TestRegenViewsAllThree (2 integration), TestDoctorViewsSubcommand (5 subprocess + 1 JSON-shape). Public-function coverage test (`test_every_public_lib_function_referenced_in_some_test`) confirms `plan_regen`/`apply_regen`/`run_views_command` have direct test references, not just transitive.

**Dogfooded:** regen-views against the framework's own change-log produced `.prawduct/release-notes.md` with v1.3.17 + v1.3.16 sections and appended `scope_rollups:` to `.prawduct/project-state.yaml` with `v1.4` listing chunks 00-05 + release v1.3.17. Idempotent second run reports `Status: up to date / Release notes: up to date / Scope rollups: up to date`.

**Methodology decision recorded in change-log entry as well as in the maintenance plan:** pre-commit regen for views is *deferred* to Chunk 07 (per the F1 plan line that originally promised it). v1.4 ships **on-demand regen only** — via `product-hook regen-views` (run manually or by chunk-close governance per methodology/building.md) and `prawduct-setup.py views <dir> --refresh` (manual). The backlog note filed during Chunk 05's Critic capturing this scope-shift is now consolidated here.

## 2026-05-18: Chunk 05 — F1a derived views (work-log schema + Status view)

<!-- prawduct: chunks=05 | status=shipped | scope=v1.4 -->

**Why:** F1's load-bearing premise (one canonical store, derived views replacing hand-curated summaries) needs a working derived-view pipeline before the remaining views (release notes, scope) can land in Chunk 06 and migration tooling in Chunk 07. Chunk 05 ships the schema, the parser, the first view (build-plan Status), and the source-of-truth guardrails threaded across Critic + PR-reviewer + methodology surfaces.

**What:** New `tools/lib/views.py` (HTML-comment tag-line parser + Status-section view builder + `views_enabled` reader, stdlib-only ~216 lines). New `product-hook regen-views` subcommand reads change-log + build-plan, rewrites Status checkboxes from `status=shipped` tags. Tagged-entry schema documented in `templates/change-log.md`. Status marker added to `templates/build-plan.md`. `views_enabled` opt-in field added to `templates/project-state.yaml` (default false) and `.prawduct/project-state.yaml` (true — dogfooding). v1.3.17 and v1.3.16 entries backfilled with tag lines so the first regen against current Status is a no-op. Source-of-truth guardrails added at 8 surfaces — when `views_enabled` is true, the change-log tag is canonical and Status is derived; Critic/PR reviewer flag mismatches as WARNING. Test suite: 39 new tests in `tests/test_views.py`, 1041 total.

**Status semantic decided (2026-05-18):** `status=shipped` means "merged to mainline" — per-chunk timing. A chunk's checkbox flips `[x]` the moment its merge commit lands, independent of whether a tagged release has consolidated it yet. Release inclusion is tracked separately via the `release=vN.M.P` tag on a per-chunk or per-wave entry.

## 2026-05-18: v1.4 Wave 1 — proportional Critic + cumulative gate + foreign-API verification (v1.3.17)

<!-- prawduct: chunks=00,01,02,03,04 | release=v1.3.17 | status=shipped | scope=v1.4 -->

**Why:** Five recurring quality-governance gaps surfaced across recent product work: (F2) per-chunk Critics passed clean but cross-chunk integration cracks (helper introduced in chunk N misbehaving against prose in chunk M) only emerged at merge time, with no structural gate to catch them; (F3) build plans drift from real file paths as a chunk's scope evolves, and the Critic had no mechanical way to detect references to files that no longer exist; (F6) the Critic ran the full 7-goal protocol against every chunk regardless of work type — wasteful for docs/cleanup chunks, occasionally missing the right goals for designer-handoff chunks; (F8) chunks wrapping foreign APIs (vendor SDKs, MCP servers) routinely shipped against assumed signatures that didn't match the real surface, found at integration time. Each gap had been surfaced as a learning or backlog item over the prior quarter; v1.4's first wave addresses them in one bundle.

**What:** Five chunks delivering four new mechanisms, plus three remediation rounds dogfooded against the cumulative-Critic gate they introduce.

1. **Chunk 00 — SKILL.md trim-pass.** `agents/critic/SKILL.md` reduced 3500→3196 tokens (4-token slack against the 3200 ceiling), reclaiming headroom for the new goals added by F6/F8. No behavioral change.

2. **Chunk 01 — F2: cumulative-Critic gate (`mode: cumulative`).** New Critic mode whose scope is `git merge-base main...HEAD` rather than the chunk's own diff. Invoked via `/critic cumulative`. Records findings with mode `cumulative (bundle review, ready for merge)` to `.prawduct/.critic-findings.json`. New `tools/product-hook check-cumulative-critic` subcommand provides the structural gate that `/pr` calls before opening a PR — requires the findings file to exist, be schema-valid, be from the current session, be in cumulative mode, and have no unresolved BLOCKING findings. Pr skill (`pr/SKILL.md` Step 2) invokes this gate.

3. **Chunk 02 — F3: build-plan ref drift verification.** New `tools/product-hook verify-chunk-refs [chunk_id]` subcommand parses backticked file-path references from a chunk's `### Chunk NN:` section and verifies each path exists on disk. Critic Goal 2 invokes it; non-zero exit → BLOCKING per missing path. Supports `new \`path\`` forward-ref syntax for chunks creating new files. Scope this wave is file paths only; symbol and backlog-ID extraction backlogged.

4. **Chunk 03 — F6: chunk-Type axis for proportional Critic.** Build plans gain a `**Type:**` field (`code` | `doc-only` | `cleanup` | `designer-handoff` | `cumulative-final`, default `code`). Critic goal selection modulates by Type — `doc-only` skips test-coverage goals, `designer-handoff` skips the gate entirely (artifact-only chunks have no code to review), `cumulative-final` triggers the cumulative pass. Unknown Type falls closed to `code` (the fully-armed protocol) — escape-hatches-fail-closed default per existing learning.

5. **Chunk 04 — F8: Foreign API verification as methodology default.** Build plans gain an optional `**Foreign API:** <name>` field declared on chunks wrapping vendor APIs/SDKs whose surface the project doesn't own. Critic Goal 2 requires such chunks to include a `verify-api` step prepended as Done-when step 0 — meaning: read foreign source, run discovery probes against a live instance, or document the docs source consulted and flag Requirements Confidence: Medium. Captures the hallucinote Ableton-MCP rework pattern as a framework default.

**Remediation rounds (cumulative-Critic dogfooding itself):**

- **Round 1 (W2/W3):** Cumulative pass against the 5-chunk bundle caught two regressions chunk-Critics missed. W2: `_looks_like_file_path` (F3) emitted BLOCKING false-positive ref-drift findings on slash-command tokens (`/pr`, `/learnings`, `/critic`) — tightened the heuristic to exclude single-segment `/<cmd>` tokens with no further `/` and no `.`. W3: `Foreign API` field name diverged between methodology (`foreign_api:` snake_case in prose) and build-plan template (`**Foreign API:**` title-case) — aligned 8 surfaces on title-case (matching the existing build-plan field convention: `**Type:**`, `**Critic mode:**`, `**Requirements Confidence:**`). Two new learnings captured: cumulative-Critic finds first-use regressions chunk-Critic can't; build-plan fields use Title Case (snake_case is the YAML-key namespace in `project-state.yaml`, a different surface).

- **Round 2 (W4/W5):** Cumulative-Critic round-2 caught a fail-open contract in the gate that round-1 introduced (W4: missing `.session-start` silently bypassed freshness check, function returned 0 on any non-blocking findings — inverted to fail closed with actionable message + new test pinning the contract) and a missing-row deficit in `.prawduct/cross-cutting-concerns.md` (W5: added four rows for the new pipeline-spanning mechanisms: Foreign API verification, Cumulative-Critic gate, Build-plan ref drift, Chunk Type / proportional review).

- **Round 3:** Cumulative-Critic round-3 caught a one-cell typo in the W5 registry row (`cumulative-bump` should be `cumulative-final` — same namespace-divergence class as W3, recapitulated one row over). Fixed.

- **Round 4:** Cumulative-Critic round-4 returned 0 blocking + 0 warnings + 6 advisory notes ("Ready to merge"). Five notes filed to backlog (release-readiness gate documentation, chunk-Type error surfacing, forward-ref convention prose, F8 numbering language, fall-through fixture coverage). The dogfooding chain validated F2's premise four cycles deep.

**Test coverage:** 1002 passing (+3 over pre-wave baseline of 999). New test classes: `TestDesignerHandoffSkipsCriticGate`, `TestCheckCumulativeCriticSubcommand` (8 tests, including the W4 fail-closed regression pin), `TestParseBuildPlanChunkRefs`, `TestVerifyChunkRefsSubcommand`, `TestParseBuildPlanChunkType`. Test evidence fresh in-session.

**Compatibility — read before syncing:** The `check-cumulative-critic` gate is new structural enforcement. After syncing v1.3.17, the next `/pr create` in any product repo will require a fresh `cumulative`-mode Critic record (produced by `/critic cumulative`) covering `merge-base...HEAD` — the gate refuses to open the PR without one. This is a real behavior change at the PR boundary: workflows that previously ran chunk-Critics and went straight to `/pr` now have an additional cumulative pass before PR creation. Day-to-day chunk work is unchanged; only the PR-creation step gains the gate. The backlog item "v1.4 release-readiness: document the new `/pr create` gate before tagging" tracks adding a `prawduct-doctor` migration prompt and full release-notes section before the v1.4 minor bump consolidates this and subsequent waves.

## 2026-05-10: Janitor skill becomes model-invocable (v1.3.16)

<!-- prawduct: release=v1.3.16 | status=shipped -->

**Why:** The janitor skill shipped with `disable-model-invocation: true` in its frontmatter, which prevented the agent from launching it via the Skill tool. It still appeared in the user's slash-command list (because `user-invocable: true`), so users saw it but the agent couldn't run it — confusing asymmetry. The intent was always for the agent to be able to drive periodic maintenance, not just respond when the user types `/janitor`.

**What:** Removed the `disable-model-invocation: true` line from `.claude/skills/janitor/SKILL.md` frontmatter. `user-invocable: true` and the `allowed-tools` allowlist remain unchanged. After sync, product repos pick up the same change (the framework's janitor SKILL.md is the source for product instances per `tools/lib/core.py`).

**Also:** Bundles dogfood re-syncs of `.prawduct/build-governance.md` and `.prawduct/critic-review.md` that the session start hook applied automatically when upgrading to v1.3.15 templates (the framework repo is its own product instance, so its `.prawduct/` files lag template changes by one session-start cycle).

## 2026-05-09: Requirements Precede Code — visible/assessed requirements clarity (v1.3.15)

**Why:** Recurring quality issues across products using Prawduct trace to a common root: both user and agent get excited and start design/code before requirements are clear. The previous framework had no friction at the right boundary — Critic and PR review fire *after* code exists, by which point design is committed. Discovery was treated as a one-time phase, with each new feature implicitly skipping its own micro-discovery. The agent had no trigger to pause when the user said "build X." The cure couldn't be heavy gates (too straitjacketing) or pure principle (history shows judgment alone won't interrupt momentum) — it needed light, distributed friction that surfaces requirements clarity at multiple places without blocking.

**What:** Six interlocking changes, all in service of the same idea: make requirements clarity a visible, assessed property at every appropriate boundary.

1. **New Quality principle: Requirements Precede Code (#6).** "Code built on unclear requirements is debt the moment it's written." Sits beside Honest Confidence (#5): one is about what you know; this is about whether you understand the problem. Old principles 6-22 renumbered to 7-23; active by-number references swept across `methodology/`, `templates/`, learnings, registry, and test scenarios in both "Principle N" and "(#N)" forms. Historical files (changelog, reflections, change_log_history) left frozen per the framework's existing rule.

2. **Requirements Confidence field on build plans.** `templates/build-plan.md` now has a required section between YAML frontmatter and Status: Level (High | Medium | Low), Why (one sentence), Open assumptions / unknowns, What would raise confidence. The field is honest self-assessment, not a gate. `methodology/planning.md` documents the semantics under Build Planning.

3. **Pre-build readiness check.** `methodology/building.md` gains a "Before You Build: Confidence Check" section before The Build Cycle — three questions in one sentence each (problem, success, out-of-scope), three response options when unclear (close the gap, sketch and confirm, proceed knowingly).

4. **Recursive discovery framing.** `methodology/discovery.md` promotes "Discovery Recurs" from a buried trailing paragraph to a top-of-file section. Distinguishes initial discovery (project foundation) from feature-level discovery (the same three questions at smaller scale, captured in the Confidence field).

5. **Agent-side trigger in CLAUDE.md.** Both framework `CLAUDE.md` and `templates/product-claude.md` now have "Before Building: Requirements Clarity" sections that fire when the user says "build X" / "implement Y" / "let's add Z." Three questions, cheap close, don't interrogate (pairs with Principle 20 — Infer, Confirm, Proceed).

6. **Critic Goal 2 checks.** `agents/critic/SKILL.md` and `templates/critic-review.md` Goal 2 (Nothing Is Missing) gain two new checks: (a) acceptance criteria as observable behavior, not implementation ("function X exists" is implementation; "user can submit form and see confirmation" is behavior) → WARNING; (b) Requirements Confidence field present, with open assumptions listed if Medium/Low → WARNING. Catches overstated confidence after the fact, creating downstream pressure on the upstream framing.

**Bootstrap demonstration:** the build plan for this work itself used the new Requirements Confidence field before Chunk 02 codified it (declared "High" with an Open Assumption about exact prose for new Critic bullets). That uncertainty held: the prose got refined under token-budget pressure during Chunk 04. Useful proof that the field surfaces unresolved bits without blocking progress.

**Behavioral notes:**
- The check sits before methodology, not as a gate. No stop-hook or other enforcement blocks low-confidence plans. The forcing function is honest self-assessment plus downstream Critic visibility.
- "Don't interrogate" disclaimer in both CLAUDE.md sections explicitly pairs the check with Principle 20 (Infer, Confirm, Proceed). One inference to confirm > five questions.
- Discovery's existing closing paragraph (which mentioned recurrence) was reduced to a pointer at "Discovery Recurs" earlier in the file, avoiding duplication.
- Two token-budget bumps: `methodology/building.md` 4100 → 4250 (Before-You-Build section, ~100 tokens after aggressive trim); `templates/product-claude.md` block 2900 → 3050 (Before-Building section, ~110 tokens). Both bumps documented in test rationale matching prior bump pattern.
- `templates/skill-critic.md` is a thin launcher pointing at `.prawduct/critic-review.md`; product Critic instructions reach product repos through `templates/critic-review.md` (already updated). No edit needed there.

**Files:**

- `docs/principles.md`: new Principle 6 inserted after Honest Confidence; principles 6-22 renumbered to 7-23
- `CLAUDE.md`: inline-numbered Quality list gains entry at 6; Product/Process/Learning/Judgment clusters renumbered; new "Before Building: Requirements Clarity" section between Sessions and Methodology
- `methodology/building.md`: new "Before You Build: Confidence Check" section before The Build Cycle; principle-by-number references updated (Principle 11 → 12, 22 → 23)
- `methodology/discovery.md`: new "Discovery Recurs" section after Risk Calibration; trailing recurrence paragraph reduced to pointer; principle-by-number references updated (Principle #6 → #7, 7 → 8, 8 → 9)
- `methodology/planning.md`: new "Requirements Confidence" subsection under Build Planning
- `templates/build-plan.md`: new "Requirements Confidence" section between frontmatter and Status; principle-by-number reference updated (Principle #9 → #10)
- `templates/build-governance.md`: condensed mirror of the readiness check before the Build Cycle steps
- `templates/product-claude.md`: new "Before Building: Requirements Clarity" section in framework-managed block; Quality principle list gains "Requirements Precede Code"
- `agents/critic/SKILL.md`: Goal 2 (Nothing Is Missing) gains two bullets — acceptance criteria as observable behavior, Requirements Confidence field present
- `templates/critic-review.md`: matching dense-paragraph form for product Critic instructions
- `.prawduct/cross-cutting-concerns.md`: principle-by-number references updated (Principle 7 → 8, 9 → 10); new "Requirements clarity" row added with full pipeline coverage
- `.prawduct/learnings.md`, `.prawduct/learnings-detail.md`: `(#N)` references swept (#21→#22, #17→#18, #16→#17, #14→#15, #13→#14, #12→#13, #10→#11, #9→#10)
- `tests/scenarios/family-utility.md`, `background-data-pipeline.md`, `terminal-arcade-game.md`: principle-by-number references updated (Principle 7→8, 10→11, 22→23)
- `tests/test_v5_methodology.py`: building.md token budget 4100 → 4250 with rationale
- `tests/test_v5_templates.py`: product-claude.md block budget 2900 → 3050, total 3500 → 3650, with rationale; TestProductClaudePrinciples parametrize updated to enumerate all 23 principles (adds Principle 6, shifts subsequent)
- `README.md`: four occurrences of "22 principles" → "23 principles"
- `docs/project-structure.md`: two occurrences of "22 principles" → "23 principles"
- `.prawduct/backlog.md`: token-budget-bumps item promoted from Queue to "Active — next up" (third bump trigger fired this release)
- `VERSION`: 1.3.14 → 1.3.15
- `.claude/settings.json`: banner v1.3.14 → v1.3.15

**Post-/critic-final fixes:** the README/project-structure/test-parametrize/cross-cutting-row/backlog-promotion edits in this list landed in response to three warnings and one note from `/critic final`. The Critic catching the "22 principles" drift in user-facing docs and the test-contract drift in the principles parametrize was a clean illustration of why final-mode is needed: chunk-mode reviews scope to changed files; final-mode reads cross-cutting summaries (README, registry, test enumerations) that drift silently when a sweep misses them.

## 2026-05-08: Stale-clean detection auto-resolves false-edit syncs (v1.3.14)

**Why:** When a product repo gitignores `sync-manifest.json` (the convention for several large client projects), every fresh clone bootstraps the manifest from current on-disk hashes. After a few framework releases, those hashes drift from what current templates would produce — so `template`-strategy files look "locally edited" to sync, even when no human ever touched them. Empirically: 5 of 6 currently-stale files across `discodon` and `discodon-brooks2` were stale-clean, hiding the one file with a real edit under `--force` advice noise. The conservative skip behavior was hostile to upgrade UX precisely when the framework released improvements.

**What:** Sync now detects stale-clean files via historical template render. When a `template`-strategy file's hash doesn't match the manifest's stored hash AND doesn't match the current rendered template, sync walks the framework's git history of that template (with `--follow` for renames, capped at 100 commits, with per-sync render caching). If any historical render matches the current file content, the file is framework-produced from an older version → safe to overwrite without `--force`. Auto-resolved files emit `Auto-resolved {file} (stale-clean from {short_sha})`. Files matching no historical render fall through to the existing skip-with-`--force` behavior — no change in handling for genuine local edits.

The same classification powers `prawduct-doctor`'s `framework_currency` check, which now reports per-file class (`stale-clean` / `local-edit` / `missing`) with an action-oriented detail string and recommends the appropriate next step.

**Behavioral notes:**
- Stale-clean detection runs *before* the `--force` fallback. When a file is both stale-clean and `--force` is set, the action label is `Auto-resolved` (truer to what happened) rather than `Force-updated`. The user's `--force` intent is preserved for genuine local edits, where it's still required.
- `block_template` files (CLAUDE.md) and `always_update` files always overwrite on sync per their existing strategy — doctor classifies any drift as `stale-clean` for those. This piggybacks on the v1.3.13 marker contract change (framework owns content inside `PRAWDUCT:BEGIN/END`).
- Briefing's `Drifted templates` header renamed to `Place-once template advisories` to clarify it's about the place-once template set (project-preferences, boundary-patterns, change-log, backlog, conftest.py) — files the user owns where the framework template has evolved. Distinguishes from doctor's `framework_currency` lens, which covers the managed file set sync actively maintains.

**Files:**

- `tools/lib/sync_cmd.py`: new `_HISTORICAL_RENDER_DEPTH_CAP = 100` constant. New `_match_historical_render(fw_dir, template_rel, target_hash, subs, cache=None)` helper — walks `git log --follow --format=%H --name-only` and pairs each historical SHA with the file's path at that commit, so renamed templates are findable via `git show <sha>:<historical-path>`. Cache keyed by `(sha, historical_path)`. `run_sync()` `template`-strategy branch declares a per-sync `historical_render_cache` and calls the helper between the existing autofix and the local-edits skip.
- `tools/lib/__init__.py`, `tools/prawduct-setup.py`: re-export `_match_historical_render` and `_HISTORICAL_RENDER_DEPTH_CAP` for the legacy importlib test surface.
- `tools/lib/validate_cmd.py`: `framework_currency` refactored to classify each stale file as `stale-clean` / `local-edit` / `missing`. Detail string format: `"<N> files differ — <K1> auto-resolve on next sync (X, Y); <K2> have local edits (Z — review diff or sync --force); <K3> missing (W — sync will create)"`. Recommendations are action-oriented per class. Restart files only listed when they will actually change.
- `tools/product-hook`: briefing label renamed `Drifted templates` → `Place-once template advisories`.
- `VERSION`: `1.3.13` → `1.3.14`.
- `.claude/settings.json`: banner string `Built with Prawduct v1.3.13` → `v1.3.14`.
- `tests/test_prawduct_sync.py`: new `TestMatchHistoricalRender` (7 tests covering HEAD/mid-history match, no-match, --follow across renames, no-git fallback, depth-cap, cache hit). New `TestStaleCleanDetection` (6 tests covering auto-resolve happy path with manifest refresh, genuine-edit skip preservation, --force still works for genuine edits, stale-clean precedence over --force, mixed-batch per-file outcome, per-sync cache populated).
- `tests/test_product_compat.py`: new `TestDoctorClassification` (4 tests covering stale-clean classification, local-edit classification, mixed-class aggregation, happy path unchanged).

## 2026-05-08: `block_template` — framework owns content inside markers

**Why:** Discodon sync from v1.3.5 → v1.3.13 reported `Skipped CLAUDE.md — block has local edits` even though the local block had no user customization — it was just stale framework content from the previous sync. Investigation showed the same false-edit signal would fire on every framework upgrade for repos that gitignore `sync-manifest.json` (which bootstraps fresh per clone, recording on-disk hashes that don't match what the current template renders). The marker convention already promises "framework-owned region" (the `<!-- PRAWDUCT:BEGIN -->` / `<!-- PRAWDUCT:END -->` markers exist for exactly that purpose) but sync was treating in-block content as co-edited shared space.

**What:** `block_template` strategy now always overwrites content between the markers on sync. Content **outside** the markers (before/after) is preserved verbatim, as it always was. The `--force` flag is now a no-op for `block_template` (kept on the CLI for `template`-strategy files).

**Backwards-compat note:** Product repos with hand-edited content **inside** the markers will lose those edits on the next sync. The marker convention has always implied this contract; this change aligns sync behavior with the convention. User customization should live outside the markers.

**Files:**

- `tools/lib/sync_cmd.py`: `block_template` branch simplified from ~90 to ~50 lines. Removed the `stored_hash != product_block_hash` skip-and-`--force` codepath and the separate "Restored" drift-repair branch (those cases now collapse into a single always-overwrite splice).
- `tests/test_prawduct_sync.py`: `test_skips_user_edited_block` → `test_overwrites_user_edits_inside_block`; `test_user_edited_block_skipped` → `test_user_edits_inside_block_overwritten`; `test_force_overwrites_user_edited_block` → `test_force_flag_no_op_for_block_template`; `test_restores_drifted_block` updated to match the unified action label.
- `tests/test_coverage_gaps.py`: `test_block_template_force_overwrites` → `test_block_template_overwrites_user_edits`; `test_drifted_block_restored` updated to match the unified action label.
- `README.md`: sync section now distinguishes whole-file template behavior (skip + `--force`) from block-template behavior (always overwrite inside markers, customize outside).
- `.prawduct/backlog.md`: added two follow-ups for the `template`-strategy false-edit problem (stale-clean detection via historical render; sync skip-summary line counts + `--diff` preview). Removed the now-obsolete `block_template` 3-way merge item.

## 2026-05-08: Proportional Critic — `chunk` and `final` modes (v1.3.13)

**Why:** Per-chunk Critic reviews were redoing repo-wide checks (Coherence, Design, Learnings Cross-Check, Backlog Reconciliation, README/docs scan, Framework-Specific Checks 7-10) on every chunk of a multi-chunk build plan, each taking 4-10 min on large repos. A 5-chunk plan paid 25-50 minutes of Critic time, then `/pr` invoked the PR reviewer to do most of the same checks again over the full diff. Most of that work was redundant: chunk-local correctness (Goals 1-3) catches the high-frequency failures (fix-by-fudging, dropped requirements, broad exceptions) and is cheap; the cross-cutting goals need the full session diff to do their job and belong at end-of-cycle, not on every chunk.

**What:** Two named Critic modes, declared per chunk in the build plan:

- **`chunk`** — Goals 1-3 only, single-pass, scoped to the chunk's uncommitted diff. Skips coordinator pattern, Learnings Cross-Check, Backlog Reconciliation, README scan, Framework-Specific Checks. Target 1-2 min.
- **`final`** — all 7 goals + cross-checks + Framework-Specific Checks. Coordinator pattern eligible for medium/large work. Target 4-10 min.

**Caller-side / persisted-side split:** The slash-command argument and build plan field use the short token (`chunk` / `final`) for ergonomics. The `mode` field persisted in `.prawduct/.critic-findings.json` uses the verbose form (`"chunk (lighter pass, not ready for push)"` / `"final (full review, ready for push)"`) so session briefings, gate WARNINGs, and anyone reading the JSON sees the implication without consulting docs. The hook validator rejects bare short tokens in the persisted form so writer drift surfaces immediately.

**Files:**

- `agents/critic/SKILL.md`, `templates/critic-review.md`: new `## Modes` section, mode-aware activation steps, JSON schema example with verbose `mode`.
- `agents/critic/review-cycle.md`: `## Mode Selection` and `## Per-Mode Behavior` sections; updated "When Review Is Required" matrix.
- `.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`: `argument-hint: chunk | final` in frontmatter; `$ARGUMENTS` parsing in body; default-to-`final` rule.
- `templates/build-plan.md`: chunk template adds `**Critic mode:** [pick one: chunk or final]`; standard Done-When step 2 reads `/critic <mode>`; Governance Checkpoints adds `**Commit & PR cadence:**`.
- `methodology/planning.md`: new `### Critic Mode Per Chunk` subsection (heuristic, per-chunk-commit contract, fail-safe default).
- `methodology/building.md`: build-cycle Critic step reads `Critic mode:`; new `### Modes` subsection under `## The Critic`; new "Skipping `final` mode" Common Trap.
- `templates/build-governance.md`: build-cycle Critic step references the mode field for product repos.
- `tools/product-hook`: module-level constants `_CRITIC_MODE_CHUNK`, `_CRITIC_MODE_FINAL`, `_CRITIC_MODE_VALUES`. `validate_critic_findings()` accepts records with verbose `mode` (chunk or final) or no mode field; rejects bare short tokens, unknown strings, non-string values. New `_count_build_plan_chunks(prawduct_dir)` helper. New `_critic_session_satisfies_gate(prawduct_dir)` helper — returns `(False, reason)` when a multi-chunk plan has all chunks `[x]` but the latest review was chunk-mode. `cmd_stop` wires the helper as Gate 2.5 (advisory NOTE on stderr, not blocking).
- `VERSION`: `1.3.12` → `1.3.13`.
- `tests/preferences/test_critic_skill_structure.py`: new file with 27 structure tests across `TestCriticModeDocumentation`, `TestCriticVerboseModeStrings`, `TestCriticSkillEntryPoints`, and `TestProportionalCriticMethodology`.
- `tests/test_product_hook.py`: new `TestCriticModeGate` class (15 tests covering the satisfies-gate helper, `validate_critic_findings` mode validation, and end-to-end stop-hook advisory output).
- `tests/test_v5_methodology.py`: SKILL.md token budget bumped 3500 → 3700; building.md token budget bumped 3900 → 4100. Both with in-line rationale comments and a "prefer trimming next time" reminder.

**Verification:** 894 → 937 tests passing, 0 failed (43 new). All three chunks of the proportional-Critic build plan shipped under the new modes (Chunks 01-02 used `chunk` mode at 3-4 min each; Chunk 03 will use `final` mode for end-of-cycle synthesis). The mode contract is self-applied: this build plan declared `Critic mode:` per chunk before the field was formalized in the template, and the template change in Chunk 02 retroactively conformed.

**Backwards-compat note:** Existing product repos see no breakage. Build plans without a `Critic mode:` field default to `final` (fail-safe to thoroughness). Legacy `.critic-findings.json` records without a `mode` key are still valid (the validator continues to accept them; the gate helper treats them as final). Slash-command invocation `/critic` (no argument) still works — the Critic agent defaults to `final` when `$ARGUMENTS` is empty or unrecognized. The advisory gate is non-blocking, so even product repos that miss the mode contract entirely continue to pass governance — they just won't get the speedup.

## 2026-05-05: Test-evidence schema validator + field rename `test_command` → `command` (v1.3.12)

**Why:** `tests_are_current()` in `tools/product-hook` reads `.prawduct/.test-evidence.json` via `.get()`, so writer typos like `ran_at` for `timestamp` or `num_passed` for `passed` parsed silently as "no failures, no timestamp" — failing the freshness check for the wrong reason and burying the actual bug. A discodon-brooks2 build session (commit `3403d23`) added a schema validator to its local product-hook to catch this loud, then asked for the change to be upstreamed so the framework's per-session sync would stop reverting it. Audit also surfaced a documentation/code split: `templates/build-governance.md` documented the field as `test_command`, but the validator (and 3 of 4 sampled real product repos) used `command`. Reconciled to `command`.

**What:**
- `tools/product-hook`: new `_EVIDENCE_REQUIRED_FIELDS` table (`timestamp: str`, `passed: int`, `failed: int`, `skipped: int`, `duration_seconds: int|float`, `command: str`) and `_validate_evidence_schema()` helper. Wired into `tests_are_current()` between the JSON-parse check and the existing fail/timestamp checks, so `test-status` surfaces missing-field and wrong-type errors by name. New `validate-evidence` subcommand exposes the schema check standalone for CI / pre-commit usage; exit 0 = `valid`, exit 1 prefixes stderr with `missing:` / `unreadable:` / `invalid:` / "evidence is not a JSON object" depending on the failure mode. Missing-field check returns before wrong-type check so a single fix-it pass addresses higher-priority repairs first.
- `templates/build-governance.md`: JSON example renamed `test_command` → `command`. New "Required vs. recommended" sentence distinguishes validator-required fields from recommended metadata (`git_sha`, `total`) and free-form extras (`chunk`, `branch`, `notes`) which remain allowed.
- `tests/test_product_hook.py`: existing `TestTestStatus` fixtures updated to include `skipped`, `duration_seconds`, `command` (the new strict schema rejects evidence missing any of them). New `test_schema_violation_surfaces_in_test_status` confirms the schema check fires before the freshness fallback. Two new classes — `TestValidateEvidenceSchema` (8 cases: full-valid, extra-fields-allowed, float duration, single missing field, multiple missing fields sorted+joined, single wrong type, multiple wrong types semicolon-joined, missing-takes-precedence-over-wrong-type ordering) and `TestValidateEvidenceSubcommand` (5 cases: missing file, unreadable JSON, non-dict root, schema-invalid, valid). Helper `_valid_evidence()` produces a fully-schema-valid baseline so tests construct the violation case rather than the whole dict.
- `VERSION`: `1.3.11` → `1.3.12`.

**Verification:** 880 → 894 tests passing, 0 failed (14 new). Smoke tests pass: a `.test-evidence.json` with `"ran_at"` (typo) instead of `"timestamp"` → `python3 tools/product-hook test-status` exits 1 with `stale: evidence missing required field(s): timestamp`; the framework's own freshly-written `.test-evidence.json` validates clean via `validate-evidence`.

**Backwards-compat note:** Product repos with an existing `.test-evidence.json` written under the old documented schema (`test_command` instead of `command`) will report stale on the first session post-upgrade because `command` is now required. Recovery is one re-run of the test suite — no migration tooling is shipped because the cost is low and the alternative (auto-rewriter at sync time) adds permanent surface for a one-time event. Products that already use `command` (verified: discodon, discodon-evals, discodon-brooks2) see zero impact.

## 2026-05-01: Structured Framework Freshness briefing block + anti-conflation guidance

**Why:** A discodon session (running against this prawduct dir) was asked "is prawduct updated?" and produced a wrong answer: it claimed `last_sync 2026-04-23 predates v1.3.10 (committed 2026-04-21)` (logically inverted), and conflated commit-level drift (today's unversioned commit `5885600`) with version-level drift (which didn't exist — discodon already had v1.3.10). Three independent facts (last_sync timestamp, framework version, template advisory) got synthesized into one wrong narrative. The briefing's existing `Advisories: 1 template(s) have new content` line gave the agent only enough information to improvise — and it improvised badly.

**What:** The fix has two parts that reinforce each other:

(1) **Structured freshness facts in the session briefing** — replaces the one-line advisory with a `Framework freshness:` block that pre-computes and presents:
- Framework HEAD short SHA + date + version
- Last-sync commit + date + version (read from manifest)
- Commit delta (computed via `git rev-list --count last_sync_commit..HEAD`, or "unknown" for legacy manifests without `framework_commit`)
- Version delta (when versions differ)
- Drifted templates with their causing commit, date, and subject

The agent now reads facts, doesn't derive them. Surfaces only when there's drift to reason about (commits behind, version delta, or drifted templates) — silent when in sync.

To support this, sync now records `framework_commit` (short SHA of fw HEAD) in `sync-manifest.json` at sync time. Old manifests will populate the field on next sync. Template-drift advisories are enriched with `last_changed_commit`, `last_changed_date`, and `last_changed_subject` via `git log -1 -- <template>` against the framework dir. All git lookups degrade gracefully — when fw_dir isn't a git repo or git is unavailable, fields are empty strings or None, and the briefing renders an "unknown" delta or falls back to the simple advisory list.

(2) **Anti-conflation section in `templates/product-claude.md`** — a new `Framework Freshness` subsection names the three drift dimensions (version / commit / template) explicitly and warns against synthesizing them into "on/off latest". Adds ~50 tokens; required bumping the block budget from 2,800 to 2,900 (deliberate revision, documented inline in the test).

**Verification:** 851 → 880 tests passing, 0 failed. 17 genuinely new tests + 12 inherited reruns (the two new sync test classes inherit `TestRunSyncPlaceOnce`'s 6 setup-validation tests, matching the existing `TestRunSyncTemplateDrift` pattern):
- `TestComputeFrameworkFreshness` (4 new) — manifest extraction, legacy-manifest handling, malformed-JSON guard
- `TestBriefingFreshnessBlock` (6 new) — in-sync silence, commit delta, version delta, drifted-template rendering with commit info, legacy fallback, no-freshness fallback
- `TestSyncRecordsFrameworkCommit` (2 new + 6 inherited) — manifest field written when fw is git, omitted when not
- `TestAdvisoryEnrichment` (2 new + 6 inherited) — last-changed-commit fields populated when fw is git, empty when not
- `TestProductClaudeFreshnessSection` (3 new) — section present, names three dimensions, warns against synthesizing

**Known gap caught during build:** Initial pass missed three early-return paths inside `try_sync` that still returned 2-tuples; subprocess-based hook tests caught it via `ValueError: not enough values to unpack`. Fix was mechanical — converting all returns to 3-tuples — but the lesson is that signature changes need a grep-the-callsites step that's local to the function being changed, not just at import boundaries.

## 2026-05-01: Project-preferences enforcement framework — first generators (batches 1 + 2)

**Why:** Project preferences quietly become aspirational when nothing checks them. Audited prawduct's own `project-preferences.md` against the codebase, found drift (overstated `__future__` rule, stale test-mirroring example, missing Workflow / Parallelization / Testing-strategies fields, no `tools/lib/` mention). After updating the file to current reality, built the first eight enforcement artifacts in two batches to validate the four-mechanism model (Test / Linter / Critic / Session config) on a diverse set of preference shapes.

**What:**
- Updated `.prawduct/artifacts/project-preferences.md`: corrected drifted claims; added Workflow / Parallelization / Testing-strategies fields; expanded File organization to call out `tools/lib/`; sharpened the Error-handling preference with concrete "boundary" examples for Critic adjudication; added explicit Subprocess safety preference (no `shell=True`) under Tooling; added explicit public-function coverage expectation under Testing; added an Enforcement section that maps each preference to its mechanism (Test / Linter / Critic / Session config).
- Added `tests/preferences/` with six tier-2 enforcement tests (13 test cases total) spanning six different shapes:
  - `test_future_annotations.py` — every implementation file in `tools/` and `tests/` begins with `from __future__ import annotations`. Shims auto-detected via the `Backward-compat shim` docstring marker; `__init__.py` and `tests/conftest.py` are explicit exceptions. Self-guards by asserting exception list still references real files. *Shape: AST first-statement check.*
  - `test_parallelization_config.py` — verifies `pyproject.toml` addopts contain `-n auto` and `--dist loadfile`, plus `tests/conftest.py` defines `pytest_collection_modifyitems` and applies `xdist_group` markers. *Shape: TOML/text presence check.*
  - `test_sync_only_architecture.py` — no `async def`, no `import asyncio` anywhere in `tools/` or `tests/`. *Shape: AST recursive walk.*
  - `test_subprocess_safety.py` — no `subprocess.{run,check_output,check_call,call,Popen}(..., shell=True)`. Security-relevant. *Shape: AST call-pattern (Attribute func + keyword args).*
  - `test_test_location.py` — no `test_*.py` files outside `tests/`. Catches files that pyproject's `testpaths` would silently skip. *Shape: file-tree walk.*
  - `test_public_function_coverage.py` — every public function in `tools/lib/` is referenced in at least one test. Exemption list (currently `log`, `load_json`, `strip_test_tracking`, `generate_sync_manifest`) for transitively-tested helpers, with documented resolution path. *Shape: cross-file consistency check.*
- Added matching Enforcement section stub to `templates/project-preferences.md` so new product repos inherit the discipline.
- Critic-enforced preferences (naming, error-handling, class-based grouping, etc.) live in the body of `project-preferences.md` and are adjudicated via the existing Critic Goal 4 (Project Preferences) check.

**How mechanisms were chosen:**
- Tier 1 (Linter) — naming. Prawduct has no linter configured; classifier escalates these to Critic rather than generating a weak AST test that mimics ruff `N` rules. Demonstrates the refusal path.
- Tier 2 (Test) — six preferences spanning six AST/filesystem shapes (above). The `test_public_function_coverage.py` test was tightened mid-implementation after the Critic flagged identifier-bag heuristics as a false-confidence trap; final detection requires `Attribute.attr` or `Name` in `Call.func` position only, with explicit limitations documented in the test docstring. Demonstrates the framework's own guardrail biting back during validation.
- Tier 3 (Critic) — error handling, naming, class-based grouping. "Boundary" / "appropriate" / "sensible grouping" require judgment.
- Tier 4 (Session config) — Workflow values (Branching, PR creation, PR merge) read by `building.md` / `/pr` at decision points. Not test-enforced because they govern session behavior, not code shape.

**Verification:** `python3 -m pytest tests/` → 851 passed, 0 failed (838 baseline + 13 new across `tests/preferences/`). `tools/product-hook test-status` → exit 0.

**Out of scope / backlog:**
- Audit public-function coverage exemptions (4 entries) — decide rename-to-private vs add-direct-test for each.
- Lift "assign a mechanism per preference" pattern from the artifact + template into `methodology/discovery.md` / `planning.md`.
- Workflow values are documented but lack a schema/validator (e.g., allowed values for `Branching`).

## 2026-04-21: Self-heal stale product_name on every sync + Critic/Janitor state-machine guidance (v1.3.10)

**Why:** Two separate issues.

(1) v1.3.9 fixed bootstrap but not ongoing sync — legacy manifests (bootstrapped before v1.3.9, or whose `product_identity.name` was renamed after init) kept the wrong cached `product_name` forever because `run_sync` read from the manifest and never re-consulted the committed `project-state.yaml`. Old clones that pulled v1.3.9 still saw banner churn on every sync. The manifest had two sources of truth for the product name (the cache and the committed identity block) with no reconciliation.

(2) Cross-product reflection surfaced a recurring anti-pattern: Claude repeatedly implements state-based problems (phases, modes, lifecycle stages, views, connection status, workflow steps) through interdependent booleans and scattered conditionals without making the states, transitions, or invariants explicit — producing code where invalid combinations are reachable and recovery paths have no known-good condition to return to. The framework had no check for this.

**Changes:**
- `tools/lib/sync_cmd.py` — `run_sync` now computes `product_name` as `infer_product_name(product) or manifest.get("product_name") or product.name`, making `project-state.yaml` the source of truth and the manifest cache a fallback for legacy manifests without an identity block. When the cache diverges from the committed identity, sync overwrites the manifest entry and emits an action so the correction is visible and persisted.
- Three regression tests in `tests/test_prawduct_sync.py`: self-heal corrects divergence, no-op when manifest and identity agree, fallback to manifest when identity is absent.
- `agents/critic/SKILL.md` and `templates/critic-review.md` — Goal 7 (The Design Is Sound) gains an **Unmodeled state-based problems** bullet. Framed around recognizing when a problem is inherently state-based (discrete conditions govern valid operations; correctness requires every reader to agree on the current condition) and what must be explicit (enumerated conditions, valid/invalid transitions, single source of truth for "what condition are we in"). Implementation-agnostic — enum, class, protocol, reducer, type, schema, or doc all qualify. Severity thresholds: BLOCKING when invalid combinations are reachable and cause correctness/safety failures, WARNING when ≥3 interdependent state signals span multiple call sites with no central model, NOTE for borderline cases (backlog candidates).
- `.claude/skills/janitor/SKILL.md` — Code Health theme gains a parallel bullet for surfacing these patterns during periodic maintenance.
- `methodology/building.md` — pulled back under its 3900-token budget (4062 → 3877) by removing a redundant "no pre-existing exception" paragraph (the same rule is stated in the Clean Baseline bullet, Test Discipline section, and Common Traps entry), tightening Context Compaction, Session Scope Discipline, and Critic-section prose. No rule removed; same meaning in fewer words. The budget overflow had been shipping since v1.3.8 and was surfacing as a test-suite failure across product repos.

**Blast radius:** `tools/lib/sync_cmd.py`, `tests/test_prawduct_sync.py`, `agents/critic/SKILL.md`, `templates/critic-review.md`, `.claude/skills/janitor/SKILL.md`, `methodology/building.md`. 838 tests pass, 0 failing.

## 2026-04-19: Fix banner churn across repo clones with different directory names (v1.3.9)

**Why:** Users working in multiple clones of the same product repo (e.g. `my-app` and `my-app-feature`) saw `.claude/settings.json` get rewritten to a different product-name banner on every session start, producing a permanent dirty diff that had to be ignored or repeatedly reverted. Root cause: `.prawduct/sync-manifest.json` is gitignored, so bootstrapping ran on every fresh clone; the bootstrap product-name parser scanned for a top-level `product_name:` key that never existed in the template (the actual layout is `product_identity.name:`), so it silently fell back to the directory name and baked that into the `{{PRODUCT_NAME}}` banner substitution.

**Changes:**
- `_bootstrap_manifest` in `tools/lib/sync_cmd.py` now calls the existing `infer_product_name()` helper, which correctly reads `product_identity.name` from the committed `project-state.yaml`. Directory-name fallback is preserved for repos missing the identity block.
- Updated `test_bootstrap_infers_product_name_from_state` to use the real `product_identity.name` layout with a regression comment; the product dir and identity now deliberately differ so the test pins the fix.

**Blast radius:** `tools/lib/sync_cmd.py`, `tests/test_prawduct_sync.py`. 832 tests pass.

## 2026-04-17: Session-timestamp freshness + lag warning for stale product-hooks (v1.3.8)

**Why:** Two related session-start staleness defenses. (1) The old fingerprint system (HEAD SHA + dirty file content hashes) caused chronic false positives: any commit — even metadata-only — invalidated test evidence, wasting cycles on re-runs and "benign fingerprint drift" warnings. (2) Discodon session today showed `fingerprint drift (55ae5158c4e1 -> b27c1100a6db)` despite the framework having replaced fingerprints — the product was pinned at v1.3.7 and its local `tools/product-hook` was the old code, but nothing warned about it. Product repos can silently run stale hook code when the session-start auto-sync doesn't apply.

**Changes:**
- **Trust-the-cycle freshness check** — Removed `compute_test_fingerprint()`, `hashlib` import, and ~70 lines of hashing logic from `tools/product-hook`. Evidence is current if it was recorded during the current session with all tests passing. 10 doc/template files updated to teach the new model; 3 moot backlog items removed.
- **Bidirectional framework version check** — `_check_framework_version` in `tools/product-hook` now also warns when the framework's `VERSION` is *newer* than the manifest's `framework_version` (previously it only warned in the stale-framework direction). Message names both versions and prints the exact `prawduct-setup.py sync` command so the fix is copy-paste. Fires when auto-sync at session start didn't apply for any reason (sync failed, framework unreachable, manifest not updated).
- **Test** — `test_product_lags_framework_warns` in `tests/test_coverage_gaps.py` covers the new direction using a no-op sync script so the manifest stays stale, mirroring the existing `test_stale_framework_warns` pattern.

**Blast radius:** `tools/product-hook`, `tests/test_product_hook.py`, `tests/test_coverage_gaps.py`, 10 doc/template files. 832 tests pass.

## 2026-04-15: Shift reflection cadence to work boundaries (v1.3.7)

**Why:** Product sessions were hitting friction when the user said "ready to /clear" — Claude almost always replied "wait a minute, let me write the reflection" and kept the user waiting. The old cadence ("reflect before session end") also produced rushed reflections written under time pressure.

**Changes:**
- `methodology/reflection.md` — "When to Reflect" reframed around work boundaries (chunk-end after Critic, bug fix, error recovery, judgment call, PR merge). Session-end becomes synthesis, not from-scratch. Capture step now distinguishes `.session-reflected` (per-cycle narrative) from `learnings.md` (durable rules).
- `methodology/building.md` — Build cycle "Reflect" step says "now, not at session end." Session Scope Discipline checklist step 6 is "reflection synthesis" over a file that's already populated.
- `CLAUDE.md` — Learning Loop section leads with the work-boundary cadence.
- `tools/product-hook` — Reflection-missing blocker message teaches the new cadence.
- Templates (`templates/product-claude.md`, `templates/build-governance.md`) — same reframing propagated to product repos via sync.

Hook behavior is unchanged — it already checked `.session-reflected` exists with ≥50 chars. The fix is methodological: when reflection happens at chunk boundaries, the file is already populated by the time the user asks for `/clear`, and handoff becomes fast.

**Blast radius:** 5 framework files + 2 product templates. 832 tests pass. Token-budget tests caught bloat twice and enforced tighter prose.

## 2026-04-15: Fix chronic "stale test evidence" false positive (v1.3.6)

**Why:** 8+ product sessions reported the Critic almost always warning "stale test evidence SHA — expected timing". Root cause: `compute_test_fingerprint()` hashed every dirty path from `git status --porcelain` without filtering framework/session metadata. Between the Verify step (fingerprint written) and the Critic step (fingerprint re-checked), the builder routinely touches `.prawduct/.critic-findings.json`, `.prawduct/backlog.md`, `.prawduct/artifacts/build-plan.md`, `.claude/settings.json`, etc. — normal build-cycle churn that has no bearing on test results. The fingerprint changed, the Critic flagged it, every time.

**Changes:**
- `compute_test_fingerprint()` in `tools/product-hook` now skips paths matching `_is_metadata_path()` (the same filter already used by `git_has_session_changes()` and `_session_changes_are_doc_only()`). Prefixes: `.prawduct/`, `.claude/settings.json`, `.claude/skills/`, `tools/product-hook`.
- New regression test `test_metadata_changes_do_not_invalidate_fingerprint` in `tests/test_product_hook.py` asserts identical fingerprints for (src-only dirty) vs (src + multiple metadata files dirty).

**Blast radius:** 2 files (product-hook, test file). 832 tests pass.

## 2026-04-13: Property-based testing guidance + template drift advisory system (v1.3.5)

**Why:** Property-based testing guidance was orphaned in a single test scenario file — no PBT knowledge flowed to product repos through templates, sync, or governance. Separately, the framework had no mechanism to notify existing products when place-once templates improved (test-specifications, project-preferences, conftest.py were fire-and-forget).

**Changes:**
- PBT guidance added to synced templates (build-governance, critic-review, Critic SKILL) — NOTE-level check in Goal 1, domain-conditional guidance in build cycle
- PBT content added to place-once templates (test-specifications Property-Based Tests section, project-preferences Testing strategies field, conftest.py Hypothesis config block)
- Template drift advisory system: place-once template hashes tracked in sync manifest, drift detection on each sync, advisories surfaced in session briefing
- Janitor skill: new Template Currency investigation theme, framework health pre-check, hash-update guidance after review, `templates` scope shorthand
- Methodology: discovery surfaces domain-driven testing strategies, building.md "Test strategies match the domain" principle, cross-cutting concerns updated
- Place-once mapping constants extracted to core.py (PLACE_ONCE_TEMPLATES, PLACE_ONCE_COPY)

**Blast radius:** 18 files. Templates (6), tools (3), tests (5), methodology (2), agents (1), cross-cutting concerns (1). 43 new tests, 831+ total.

## 2026-04-07: Doc-only gates, gate waivers, test fingerprint, defensive untrack, worktree awareness (v1.3.4)

**Why:** Four user-reported friction points: (1) docs-only sessions were tripping the Critic and PR gates even though there was no code to review; (2) tests were being re-run unnecessarily by builders, the Critic, and the PR reviewer because saved evidence used `git_sha` alone, which can't track uncommitted edits; (3) `.session-handoff.md` and other session files were causing merge conflicts in product repos when they had been accidentally committed before being gitignored — sync had a fix but only on next sync; (4) agents working in git worktrees reported that `git_has_code_changes()` ignored the session baseline and that the hook was not surfacing worktree state.

**Changes:**
- **Doc-only skip + waivers:** `cmd_stop` now skips Critic and PR gates when all changed files are `.md` (using the existing `_session_changes_are_doc_only`). Agents can also write `.prawduct/.gates-waived` (JSON: `{"critic": "reason", "pr": "reason", "reflection": "reason"}`) to declare a gate N/A for the current session. Empty reasons are rejected as a guardrail. The file is auto-deleted on `cmd_clear` so waivers never carry across sessions. The hook prints `GATE WAIVERS:` and the reason for each skipped gate in stderr.
- **Test fingerprint:** `compute_test_fingerprint()` returns sha256 of (HEAD SHA + sorted dirty file paths + each dirty file's content hash). `.prawduct/.test-evidence.json` gets a new `fingerprint` field. New subcommand `python3 tools/product-hook test-status` prints `current` (exit 0) or `stale: <reason>` (exit 1) — single source of truth for builders, the Critic, and the PR reviewer to decide whether re-running the suite is necessary. Falls back to git_sha-only comparison for older evidence as long as the working tree is clean.
- **Defensive untrack:** `cmd_clear` now runs `_untrack_session_files()` on every session start, mirroring `untrack_gitignored_files()` from `tools/lib/core.py`. This means product repos that have an accidentally-committed session file get cleaned up at session start regardless of whether sync ran. List is duplicated in `_SESSION_GITIGNORED_PATHS` (product-hook is intentionally standalone); a parity test in `test_coverage_gaps.py` keeps the two lists in sync.
- **Worktree fixes:** `git_has_code_changes()` now delegates to `git_has_session_changes()` so it consults the session baseline and skips pre-existing dirty state — previously it treated every non-`.prawduct/` line as a "code change" since session start, which fired the Critic gate against pre-existing dirt. New `_detect_worktrees()` helper inspects `git worktree list --porcelain` and surfaces a "Worktrees:" line in the session briefing when more than one worktree is attached, naming the active branch+path and listing the others. Agents are warned that gates only see the active worktree.
- **Docs:** `templates/build-governance.md`, `templates/critic-review.md`, `templates/pr-review.md`, `agents/critic/SKILL.md`, `agents/pr-reviewer/SKILL.md`, `templates/skill-critic.md`, and `.claude/skills/pr/SKILL.md` updated to teach the `test-status` check and the waiver pattern.
- **Tests:** Added `TestDocOnlySkipsCriticGate`, `TestGatesWaived`, `TestTestStatus`, `TestDefensiveUntrackOfSessionFiles`, `TestGitHasCodeChangesUsesBaseline`, `TestWorktreeBriefing`, plus `TestProductHookGitignoreMirror` (parity guard).

## 2026-04-04: Fix overzealous stop hook and build plan git tracking (v1.3.3)

**Why:** The stop hook was firing the Critic gate against completed plans (all `[x]` chunks) and against housekeeping changes that shouldn't trigger a code review. Build plans were also tracked in git despite being ephemeral working artifacts, causing merge conflicts when multiple branches each wrote to the same path.

**Changes:**
- Gitignored `build-plan.md` in this repo and all product repos via `GITIGNORE_ENTRIES` — build plans are ephemeral working artifacts, not permanent specs
- Stop hook Critic gate now checks for *active* (incomplete) chunks instead of file existence — completed plans (all `[x]`) and housekeeping changes no longer trigger false blocks
- Added `_has_active_build_plan_file()` helper; updated both clear and stop hook gate checks
- Updated tests to use plans with real Status sections; added `test_completed_build_plan_skips_critic`
- VERSION bump was missed in the original commit (a4696d6) and is backfilled here

## 2026-04-03: Stop tracking test counts as static artifacts (v1.3.2)

**Why:** Test count is derived data — it changes every time a test is added or removed. Storing it in static artifacts (project-state.yaml, CLAUDE.md, learnings.md) creates constant reconciliation work: the Critic flags discrepancies, and developers spend real time updating numbers that have no value over the hook's dynamic count.

**Changes:**
- Removed "test counts" from the artifact-update guidance in `methodology/building.md` and `build-governance.md` (template + instance)
- Removed "test counts" from the Critic's bidirectional freshness check (`agents/critic/SKILL.md`)
- Removed "update test count" from the janitor's task list (`.claude/skills/janitor/SKILL.md`)
- Removed `build_state.test_tracking` from the framework's own `project-state.yaml`
- Added `strip_test_tracking()` migration step to `tools/lib/migrate_cmd.py` — removes stale `test_tracking` from existing product repos on next migrate/sync

## 2026-04-01: Embed Critic review in build plan chunks (v1.3.1)

**Why:** Critic review was being skipped or offered as optional despite explicit behavioral instructions in CLAUDE.md. Behavioral instructions degrade under context pressure; the build plan — which Claude actively follows step by step — had no Critic step at all.

**Changes:**
- Build plan template: each chunk now has "Done when" steps (acceptance + `/critic` + commit)
- Removed "do not ask, do not offer" behavioral instructions from CLAUDE.md, product-claude.md, build-governance.md
- Replaced with plan-following instruction: "Follow the plan — the Critic step is there"
- Stop hook blocker message now references the build plan's "Done when" steps
- Build governance step 9 ties chunk `[x]` marking to "Done when" completion

## 2026-03-30: Extracted lib modules, framework version tracking, reflection gate improvements (v1.3.0)

**Why:** The monolithic setup script was difficult to test and maintain. Framework version tracking was needed so product repos can detect when they're out of sync. The mandatory reflection gate was blocking exploratory/Q&A sessions that had no build work to reflect on.

**Changes:**
- Extracted `tools/lib/` modules (core, init, migrate, sync, validate) from monolithic setup script
- Framework version tracking — sync records `framework_version` in manifest; session start warns if `../prawduct` is stale relative to last sync
- Reflection gate is now advisory (not blocking) when no build plan is active — exploratory/Q&A sessions no longer require mandatory reflection
- Comprehensive test coverage for all user onboarding journeys (750 tests)
- V4_GITIGNORE_ENTRIES now matches GITIGNORE_ENTRIES (adds `.session-handoff.md`, `.test-evidence.json`, `.pr-reviews/`)
- Critic changelog scope — only checks entries from current changeset, not historical entries
- Gitignore hygiene — sync removes managed files from .gitignore if incorrectly added
- Deprecation warnings when migrating v1/v3/partial repos

**Classification:** structural

## 2026-03-28: Structural Critic tool restrictions, test evidence, and auto-invocation (v1.2.9)

**Why:** The Critic repeatedly ran the full test suite (10K+ tests) despite instructions not to — behavioral constraints lose to safety goals when the agent has unrestricted Bash access. Additionally, builders treated Critic review as optional, offering it as a user choice rather than running it automatically.

**Changes:**
- Critic is now a proper Claude Code skill (`.claude/skills/critic/SKILL.md`) with `allowed-tools` that structurally prevent running tests, builds, or executables. Uses `context: fork` for independent review.
- Test evidence mechanism: builder records results to `.prawduct/.test-evidence.json` during Verify; Critic reads evidence instead of re-running tests.
- Strengthened Critic invocation language: "Run `/critic` now — do not ask the user, do not offer it as an option."
- Stop hook skips reflection gate for doc-only (.md) changes.

**Classification:** governance

## 2026-03-22: Make project-state.yaml merge-friendly

**Why:** Multiple agents/developers working in parallel branches frequently conflict on project-state.yaml. Agents resolve by taking "ours," losing other branches' progress.

**Changes:** Branch-scoped WIP (keyed by git branch name), change_log split to separate .prawduct/change-log.md, test_count computed instead of tracked, merge conflict guidance added.

**Classification:** structural

## 2026-03-22: Consolidate init/migrate/sync into unified prawduct-setup.py

**Why:** Three scripts with importlib cross-imports, a 6-step prose detection algorithm in CLAUDE.md, no post-setup validation, and no health check tool.

**Changes:** Unified into one script with subcommands (setup, sync, validate). Added /prawduct-setup skill. Old scripts replaced with import-safe backward-compat shims. 725 total tests.

**Classification:** structural
