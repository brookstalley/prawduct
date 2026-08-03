# v3.2.0 Supported-Scenario Functional Audit

**Purpose.** The acceptance set for Chunk 09 done-when #8 — the owner's "GitHub Issues is working
great" release gate, sharpened 2026-07-28 to: *"all functional requirements working great. NFRs like
performance can lag to a later release. But we cannot be functionally broken for any supported
scenario."*

**Method.** Extracted the 55 requirement IDs from `documentation/backlog-service-requirements.md`,
mapped each to implementation (`plugin/lib/backlog/`, `plugin/bin/prawduct-hook`,
`plugin/skills/backlog/`) and to test references, then **read the code for every candidate gap**.
Grep-absence alone is not evidence — requirement IDs are not always cited in code, and two candidates
in this audit were dismissed on reading (see § Dismissed).

**Status:** first pass, 2026-07-28, **with one finding corrected after owner challenge** (F1 — see the
correction block there; the first draft wrongly claimed the whole adapter was unverified against live
GitHub). The live-verification record is substantial: VRF-004 (`verified`, 2026-07-17) absorbed the
`verify-api`/CONTRACT-1 obligation for the core issue shape, and ~200–300 items have been migrated
live more than once (SPIKE-S2, VRF-009). Read "unverified" below as scoped to the specific reader or
requirement named, never as a blanket statement.

---

## The scenarios v3.2.0 supports

Per **MG3** as clarified by the owner 2026-07-28 — cutover is **atomic within a project, staged across
the fleet**:

| # | Scenario | In scope for v3.2.0 |
|---|---|---|
| S-A | **Stay on markdown** — repo has not migrated, may never | ✅ yes (MG3 binds the markdown read path until the *last* project cuts over) |
| S-B | **Migrate** markdown → Issues | ✅ yes (Chunks 05/06) |
| S-C | **Day-to-day use** on Issues after migrating | ✅ yes |
| S-D | **Onboard** a new product | ✅ yes (Chunk 03 closed ONB-3F9P) |
| S-E | **Export / backup** | ✅ yes (MG2) |
| S-F | **File upstream** into prawduct's repo | ❌ **no** — Chunk 08 deferred; `incoming-bugs/` remains the path |

---

## Findings

### F1 — ~~Three foreign-API *readers* are fake-verified only~~ — **CLOSED 2026-07-28 (VRF-010)**

**All three work against real GitHub; the fake's shapes match.** `list_blocked_by` excluded a blocked
item from `pick` and re-admitted it when the blocker closed; `list_sub_issues` and `list_timeline`
parse correctly; `export` serialized the real native graph. **MIG-3 is live-proven for the first
time** — this run had the graph SPIKE-S2 and VRF-009 both lacked, discharging VRF-009's "UNPROVEN,
not failed." Cost: 3 issues, 2 links. BKL-3N8Q is now fully dischargeable.

One new finding fell out — see **F8**.

**Everything below this line is F1's original pre-closure text, retained verbatim for the record and
superseded by the closure above.** Read it as the state on 2026-07-27, not as current: its
present-tense claims — "what genuinely remains fake-verified", the per-reader table, "cost to close
is small" — are exactly what VRF-010 discharged. Only the blockquoted paragraph was marked as
historical before; the prose after it was not, so a reader landing mid-entry found a live-sounding
claim under a heading that says CLOSED.



> **CORRECTED 2026-07-28, owner challenge.** This finding first read *"`verify-api` has never run; the
> entire adapter is fake-verified."* **Both halves were false**, and the evidence was already in this
> repo. VRF-004 states in terms that it *"absorbs the Done-when step-0 `verify-api`/CONTRACT-1
> obligation"* and is **`verified` (2026-07-17)** against `brookstalley/prawduct-backlog-smoke`,
> capturing the raw issue shape for the fake. On top of that, ~200–300 items have been migrated live
> more than once (SPIKE-S2 2026-07-17 ~209 items; VRF-009 2026-07-24 295 items, `fidelity_ok`, 294
> aliases minted, `resume_created_duplicates: 0`). The error was generalizing BKL-3N8Q's narrow,
> accurate scope — *relationship/timeline* shapes — into a claim about the whole adapter.

**Live-proven, repeatedly** — not in question: `file`/`get` round-trip with canonical
`owner/repo#N` ids · the `prawduct` body block (`v: 1`) · `stage:`/`status:` label encoding ·
`provision` creating namespaced labels without touching pre-existing ones (GV6) · `--json` envelope
purity and SEC-1 (no token leakage) · issue numbers monotonic and never reused (M6) · `If-None-Match`
→ `304` · pagination · bulk import at ~300-item scale with fidelity intact · resume idempotency
(CRASH-4) · the paced create-then-close archive burst.

**What genuinely remains fake-verified** is BKL-3N8Q's actual scope — three *readers*, none of which
any migration or round-trip exercises:

| Reader | Why no live run has touched it |
|---|---|
| `list_blocked_by` | The importer maps `related:` to **no native edge**, so a migration creates zero dependencies — there is nothing for it to read. VRF-009 recorded `relationships_reconstructed: false` for exactly this reason. |
| `list_sub_issues` | Same — no migration path creates sub-issues. |
| `list_timeline` | Migration never reads timelines; `superseded_by` is read from the body block instead (the CC5 gap, F5). |

**Why it still matters despite the narrow scope.** These three sit behind `pick`'s blocker predicate
and the duplicate-redirect decode — the two places where a wrong shape produces *confidently wrong
output* rather than an error. `pick` is the single most-used read in day-to-day work (S-C).

**Cost to close is small**, precisely because the scope is small: create two issues in a throwaway
repo, `link` one `blocked-by` the other, and run `pick` + a timeline read against real GitHub. That
exercises all three readers in one pass — no migration needed.

### F2 — GV8 is unmet: three norm-lifecycle signals go dark at cutover

**GV8** states *"Norm-lifecycle signals survive cutover."* They do not — they retire. `norm_probes.py`
disables all three at `post_cutover(state)`:

- `revisit-due` (`:373`) — *"item liveness now lives on GitHub Issues; the file is frozen"*
- `dead-why` (`:413`) — *"dead/live can no longer be judged from the frozen file"*
- `stalled-transition` (`:459`) — *"item movement can no longer be judged from the frozen file"*

**Credit where due: this is a *documented* retirement, not a silent no-op** — each carries a comment
naming why. That is materially better than the GV7 silent-degradation failure mode, and an earlier
draft of this audit wrongly called it silent before reading the code.

But the requirement says *survive*, and restoration is **W1-gated** — BKL-4R7V records that resolving
`#N` to a live status "lands with the W1 cache under GV8, alongside the other post-cutover readers."
W1 is out of v3.2.0. So a migrated repo permanently loses three governance signals it had on markdown.

**Owner decision needed:** does an unmet GV8 block the gate, or does v3.2.0 ship with the retirement
declared in the release note? It is a *functional* requirement (governance integration), not an NFR,
so the functional-completeness ruling does not defer it on its own.

### F3 — GV9 is unmet, but **not silently**, and its "cheap half" does not exist. **[BKL-4R7V, open]**

> **CORRECTED 2026-07-28** after attempting the fix. The recommendation here was *"widen the regexes,
> it's pure syntax and doesn't need W1 — take it in v3.2.0."* **That work is a no-op.** Every consumer
> of an id regex is already gated off post-cutover, so widening changes nothing. Verified before
> writing any code.

**GV9** — *"Item references survive the identifier change."* Post-cutover the canonical id is
`owner/repo#number` and no citation surface reads it. But the reason is not a narrow regex:

- **`norm_probes._BACKLOG_ID_RE`** — the "concrete break" BKL-4R7V names — is consumed **only** by
  `probe_dead_why` (`:426`) and `probe_stalled_transition` (`:473`), and **both `return []` when
  `post_cutover(state)`**. Widening the pattern feeds a reader that never runs.
- **Critic C-B1–C-B4** (`review-cycle.md:170`) and **PR R-1/R-2** (`pr/review-protocol.md:50`) both
  skip post-cutover **and emit a NOTE saying so**.
- **No code parses `closes:` / `closed-by:`** — they are agent-read prose, and those agents are gated
  off.
- **`buildplan_refs` backlog-id verification is unbuilt** (BLD-5V8F). Nothing to widen.
- **`ids.normalize_id` already handles both spellings** — `owner/repo#42` ✅, `repo#42` ✅, and a PFX
  token is rejected *loudly* (`unrecognized ID spelling`), never silently mis-resolved.

**This materially changes how F3 should be weighed.** The PR protocol's own prose already reasoned it
through: *"every item archived at cutover still parses as open, so R-1 would flag items closed months
ago and R-2 would resolve every `closes:` against frozen history — passing or dangling with equal
confidence… A stated gap is recoverable; a confident wrong answer is not."* That is the correct call,
already made and already implemented.

So the post-cutover state is **declared-dark, not silently-blind** — much closer to acceptable than
this finding first claimed, and it is the same W1-gated restoration as F2 rather than a separate cheap
fix. **BKL-4R7V's sequencing note ("parsing can ship earlier") is wrong and should be corrected:
parsing and resolution are not separable, because the parsers only matter once the readers return.**

**Recommendation: fold F3 into the F2/GV8 ruling** — one decision about post-cutover governance
readers, not two.

### F4 — No declared terminal-markdown state. **[BKL-8W2M, open]**

Affects **S-A**, and the MG3 clarification sharpens rather than removes it. MG3 keeps the markdown
read path alive indefinitely, but there is no way for a repo to *declare* it will never migrate — so
`backlog-service-migration-required` nags it forever, routing it toward a migration it will never
perform. The repo has a supported configuration; it has no way to say so.

### F5 — CC5 out-of-band reconciliation gaps. **[BKL-9J3F, open]**

Affects S-C. **CC5** — *"the adapter tolerates and reconciles out-of-band human edits made directly in
the [GitHub UI]."* Known gaps: closing an issue as duplicate **in the GitHub UI** silently drops
`superseded_by` (the redirect is read only from the block, never the timeline); a deleted soft-facet
label decodes to `None` with no warning. Both are silent-wrong-data, the class F1 exists to catch.

### F6 — No retry budget on a `retryable: true` envelope. **[BKL-4H8P, open]**

Affects S-B and S-C. Observed live: a forked skill burned 23 attempts over 5+ minutes against GitHub
503s. A hang, not wrong data — but during a paced ~900-issue migration it is the difference between a
slow run and an apparently-wedged one (compounds with **BKL-8K2N**, the unbuilt progress heartbeat).

### F9 — Cutover is not gated on migration completeness, and a live repo is stranded because of it. **[new]**

> **Disposition recorded 2026-07-29 — ACCEPTED as discharged in a different shape than prescribed.**
> This finding asks for *"a mechanical count comparison at the point `backlog_service_repo` is
> written."* There is no code site to attach that to. The scalar has exactly two write paths:
> `init_product._record_backlog_service_repo`, a day-one scaffold where no source backlog exists to
> compare and which already **refuses** `--backlog-repo` on an existing repo ("recording
> `backlog_service_repo` on an existing repo is a cutover… not a re-scaffold"); and the operator
> hand-editing `project-state.yaml` at scrub step 6. Binding the comparison to the write would mean
> inventing a `backlog cutover` subcommand that verifies-then-writes.
>
> What shipped instead — `verify-migration` as a mechanical gate (exit 4) plus a runbook step that
> says *"Gate first — this is the one step that must not be taken on trust"* — is a defensible
> discharge, just not the one sketched here. **The honest residual: the command binds, the step does
> not.** An operator can skip prose. That gap is real and is not closed by this disposition; the
> change-log entry that claimed step 6 "gates mechanically" has been corrected rather than left
> standing.
>
> Deliberately not built for v3.2.0. If the `cutover` command is wanted, the honest trigger is *"when
> a second product cuts over"* — one product's migration does not justify the surface.

Affects **S-B**, and this is the most serious finding in the audit because it is **observed, not
theorised**: `samsung-frame-art-loader` is in the exact state MG3 says cannot exist.

**The evidence.** `backlog_service_repo` is set — so `post_cutover(state)` is True and every reader
treats `.prawduct/backlog.md` as frozen history. But that file still holds **9 open items**, and only
**2** of them (`CUI-WT3K` → #2, `TVW-4Q7M` → #3) carry an `id:PFX` alias on GitHub. The other **7 do
not exist on GitHub at all** — confirmed twice over: no alias label, and no title match against any of
the 17 issues at a generous 0.55 similarity cutoff. All 17 issues carry `prawduct` blocks, so the
other 15 are *different* work filed natively after cutover, not hand-migrated equivalents.

**7 items of live work — including a DNS-rebinding exposure and an unbounded session table — are
invisible to every reader.** Not lost: the file is intact. But nothing reads it for live state, and
they never reached the service.

**The hypothesis that had to be excluded first.** The owner proposed the benign reading: perhaps it
*is* fully migrated and `backlog.md` is stale leftover. That is exactly the shape that would make the
obvious recovery catastrophic — items re-filed by hand carry a `prawduct` block but **no** `id:PFX`
alias, so a re-import would not skip them and would mint **7 duplicates** in a store with no delete.
The title comparison is what ruled it out. **Any recovery procedure must run that comparison first.**

**The structural defect: step 6 has no precondition on step 5.** The runbook does prescribe the check
— step 5 says *"confirm every hand-minted `PFX` resolves as an `id:PFX` alias… Total issue count =
every source item"* — but it is a **human eyeball step with no tooling behind it.** `counts` reports
the GitHub side only; nothing compares it to the source. So a partial import passes unnoticed, and
then **the moment `backlog_service_repo` is set the evidence goes dark**, because the markdown stops
being read. The failure conceals itself at exactly the step that should have caught it.

> **RECOVERED 2026-07-28 (VRF-012).** The operator ran the re-import: `7 created, 2 skipped, 0
> collisions of 9`. The completeness check now returns **9 source items, 9 aliases, 0 missing** — the
> seven stranded items are #19–#25. **The instance is closed; the defect is not.** Cutover still has
> no precondition on verification, and the check that caught this is a hand-run script rather than a
> command. Everything below stands as the record of how it happened.

**Recovery for this repo (safe, verified for these specific conditions):** re-run
`import --repo brookstalley/samsung-frame-art-loader --from .prawduct/backlog.md`. It is idempotent
and keyed on the alias, so #2 and #3 skip and the 7 are created. **The backfill hazard does not bite
here** — the skip path reconciles status from markdown, which would reopen anything closed on the
service since cutover, and both #2 and #3 are `open` on GitHub *and* `open` in markdown (checked).
Scrub the 7 first if any are stale; that is an owner call.

**Fix-shape (the general defect, not this instance):** make cutover refuse when the source still holds
items with no alias on the target — a mechanical count comparison at the point `backlog_service_repo`
is written. This is the same argument BKL-9XQ2 makes about prose-only guards: step 5 is prose in the
file the operator is following, and it did not bind.

### F8 — `pick` can hand back an item closed seconds earlier. **[new, VRF-010]**

Affects **S-C**. Immediately after `status --to shipped`, `pick` returned the just-closed item as
ready work. GitHub was already correct (`state: closed`, `closed_at` set) and a direct
`issues?state=open&labels=stage:ready` query already excluded it — **this is the list-endpoint
replication window, not a filter bug**, and a re-run seconds later was correct.

Real-workflow shape: an agent closes an item, immediately picks its next task, and is handed back the
item it just finished. `file` already carries a bounded settle-retry for the documented
404-after-create window; the **close→list** path has no equivalent. Cheap fix, same mechanism.

Only a live run finds this — the fake has no replication window.

### F7 — `--help` exits 2. **[BKL-2D8N, open]**

Affects S-C and S-D discoverability. Minor, cheap, and the only source of truth for a subcommand's
flags is currently `adapter-mode.md` plus the source.

---

## Ruled out of the gate (recorded so they are not re-litigated)

| Item | Why it does not gate |
|---|---|
| **BKL-2K8V** — `pick` ~12.4 s at 209 issues, ~6× the NFR §4 floor | **NFR.** Owner ruling 2026-07-28 defers performance. W1 stays out. **Release-note obligation:** state the number so a dogfood session does not rediscover it as a surprise. |
| **AG4** — no local write queue | **NFR-A** (availability/degradation) per the NFR doc; owner ruled it lags. Verified absent — the `queue`/`flush`/`offline` matches in `plugin/lib/backlog/` are a text formatter, the migration checkpoint writer, and the offline review artifact. **Release-note obligation:** in a migrated repo a GitHub outage means no backlog at all — no reads, no writes, no fallback. |
| **MIG-3** — native-graph reconstruction unproven live | Not reachable from any supported scenario. The importer maps `related:` to no native edge, and markdown cannot express native relationships, so no migration path exercises it. Export fidelity (MG2) is separately covered. |
| **ID-4** — `node_id` across transfer | `transfer` is a W3 op, not in the slice. |
| **XP1–XP7, PV3/PV4** | S-F is out of scope (Chunk 08 deferred). |

## Dismissed on reading (grep said gap; the code said otherwise)

- **GV8's probes are not a silent no-op.** All three carry explicit `post_cutover` guards with
  explanatory comments. The gap is that they *retire* rather than *survive* — a different, smaller,
  and honestly-documented defect. Recorded because the first pass of this audit got it wrong.
- **`backlog_probes` markdown reads are not a cutover bug.** They are MG3's required behaviour — the
  markdown read path must keep working for un-migrated repos.

---

## Recommended gate-2 acceptance set

1. ~~The three relationship/timeline readers exercised live (F1)~~ — **DONE 2026-07-28, VRF-010.**
   All three verified against real GitHub; MIG-3 live-proven as a bonus. Surfaced F8.
2. **Chunk 01 VRFs** drained (VRF-005/007/008).
3. **Chunk 06** migration + VRF-006: `get`/`list`/`pick` resolve real ids, counts reconcile, a re-run
   creates no duplicates.
4. ~~F3's parsing half shipped~~ — **withdrawn 2026-07-28: it is a no-op** (every id consumer is
   already gated off post-cutover). Folded into item 5.
5. **Owner ruling on F2 + F3 together** — post-cutover governance readers (3 norm probes, Critic
   C-B1–C-B4, PR R-1/R-2) are all deliberately dark pending W1, each announcing its own gap. Block the
   release, or ship with the retirement declared in the release note? **One decision, not two.**
6. **F4, F5, F6, F7** dispositioned — each either fixed or explicitly accepted with a release-note
   line. None is currently scheduled in any chunk.
7. **Dogfood period** on prawduct's own migrated backlog with no markdown fallback.
