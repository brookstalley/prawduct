# Issue #771 — critic: decide whether governance records are review subjects: Design

`status: draft · stage: design · area: critic · added: 2026-10-13 · source: scheduled backlog session ·
issue: https://github.com/brookstalley/prawduct/issues/771`

Related: #180 (closed; item 3 is the live half), #724 (the 27-round report), #830/#941 (review-stats and
disposition surfaces this measurement reuses), `nonfunctional-requirements.md` § Direction, *"Review
rigor is stage-keyed"*.

This is a spike: its deliverable is a **ruling plus a measurement plan**, not a build. It records what the
tree already decides, which of the issue's four acceptance items that settles, and what is left to
measure. Nothing here changes code.

## Problem (restated)

The issue's evidence is a pre-fix number: records (build plans, artifacts) were 30% of the prose
findings that name only `.md`/`.yaml` files, and prose findings were 46% of file-naming findings. The
issue asks for four things: a post-fix re-measurement, a recorded ruling on whether governance records
are review subjects, an answer to #180 item 3, and either a build plan or an explicit keep-as-is.

## What the tree already decides (read 2026-10-13)

The issue was filed 2026-09-09 and treats the ruling as open. Most of it has since been decided in code
and prose, but never recorded *as the answer to this question*. Re-derive each with the command shown.

1. **Records are oracle, not subject.** `coverage_algebra.RECORD_PREFIXES = (".prawduct/",
   ".claude/rules/learnings/")` and `is_review_subject(path)` return false for them. `critic-begin`
   narrows `files_reviewed` to subjects and hands the rest over as `files_oracle` — read, not rated.
   `review-protocol.md` line 26 and `cross-checks.md` § Records Pass state it: *"Records govern review
   SCOPE, not review READING."* Re-derive: `grep -n "RECORD_PREFIXES\|def is_review_subject"
   plugin/lib/coverage_algebra.py`.
2. **A residual window is covered by one pass, with three bars.** The Records Pass, at `final` and
   `cumulative` only, rates `files_oracle` and names the set it covered. A record is a finding only if
   it **ships** (false claim to consumers), **misleads into action**, or **must stop the merge**
   (BLOCKING). Anything else "clears no bar and is **not a finding**" (`cross-checks.md`).
3. **Prose findings default to NOTE.** `review-protocol.md` § Severity: *"Prose is NOTE unless
   load-bearing"* — a test or gate reads it, or the reviewer names the concrete wrong action.
4. **#180 item 3 is answered in prose.** `review-cycle.md` § *"A re-review does not manufacture
   work"*: in `verify-resolutions`, *"a new finding is BLOCKING or it is not a finding"*; everything
   lesser is an observation (`O-n`, answerable, never a round-buying finding). The stage-keyed norm
   generalised this to every inner-stage mode. So `verify-resolutions` **does review the delta, at
   BLOCKING-only severity** — neither of the issue's two extremes. The doc states the cost plainly: the
   fix delta's own content is rated at BLOCKING only.
5. **Eligibility and cost are separate predicates.** `is_review_subject` is deliberately not the
   negation of `is_judgeable_path` (commit `429ac2df`, "eligibility stops being the negation of cost").
   Behaviour-governing prose (agent prompts, norm references, a product whose deliverable is markdown)
   stays a subject however the gate prices it.
6. **The pre-fix class mattered.** `cross-checks.md` records that 54 of 236 BLOCKING findings (23%) had a
   record as their only subject, and that record-only findings were 36% of all findings across 728
   reviews. Both are dated measurements that predate the settled structure.

## The ruling

**Governance records are not review subjects. They are the oracle, plus one bounded exception, and the
exception is the Records Pass.** Stated as a single decision so it can be cited:

> A file under a record prefix is read by every review and rated by none, except that `final` and
> `cumulative` rate it against the three Records Pass bars. A finding about a record needs a bar; a
> record inaccuracy that clears no bar is not a finding.

Why "subject" was the wrong default and "ignore entirely" is the wrong opposite: records are what Goal 2
and Goal 3 judge code *against*, so dropping them blinds the review; but rating them like code turns
each correction into a commit that re-opens coverage, which is the #180 loop. The three bars keep the
23% BLOCKING class and the false-claim-ships class and drop the rest.

This ruling needs **owner confirmation**, not just recording: it names a policy the owner escalated on
(2026-07-28, "fixing records about records has been prawduct's downfall"), and per the repo's own
learning, a governance change cannot supply its own authority. The doc proposes the wording above; it
does not ratify it.

## Acceptance status

| Acceptance item | State | What closes it |
|---|---|---|
| Post-Chunk-02 re-measure of build-plan/artifact share | **Open** — no instrument | Step 1 below |
| Recorded decision on records as subjects | **Drafted** — the ruling above | Owner confirms; then recorded (Step 3) |
| #180 item 3 answered | **Answered by shipped prose** — cite it | Step 3 records it against #180 |
| Build plan or keep-as-is | **Keep-as-is, conditional on Step 1** | Step 2 decision rule |

## What is not decided: does it still cost anything?

The remaining question is empirical. The structure is in place; whether record findings still drive
rounds after it is unmeasured. The issue's figures came from a one-session local store (907 review
facts), which this session does not have (no ledger or evidence store on a fresh clone), so **no
post-fix figure is claimed here.**

### Step 1 — measure (one script, committed, cite the command)

`tools/measure-record-findings.py`, sibling of `measure-review-loop-economy.py` (which owns ledger
parsing; import it, do not re-implement). For each `review.critic` / `review.pr` event in a window:

- Classify every finding by the paths in its `files` list: **record-only** (all under
  `RECORD_PREFIXES`, imported from `coverage_algebra`, never restated), **subject-only**, **mixed**,
  **no files**. Report the no-files share beside every figure: a finding with no `files` is invisible to
  this classification, so it bounds the answer.
- Split by **mode** (`verify-resolutions`/`chunk`/`final` vs `cumulative`/PR) and by **severity**.
- Window by plugin version, using the markers `measure-consumer-overhead.py` already carries, so the
  pre- and post-`429ac2df` eras are separated. The pre-fix era is the control; a pooled figure is the
  same mistake #829 found.
- Report the question the issue actually cares about: of reviews that **bought a follow-up round**, the
  share whose only gating or round-buying findings were record-only. Prose share of findings is the
  wrong denominator; rounds are the cost.

Red-verify before trusting a zero: feed it a synthetic ledger with one record-only BLOCKING finding and
one mixed finding and require it to count each correctly.

### Step 2 — decision rule, fixed before the data arrives

Set the threshold now so the result cannot choose its own bar:

- **Keep as-is** if, post-fix, record-only findings are under **10%** of round-buying findings in the
  boundary stage and under **5%** in the inner stage.
- **Otherwise** open a build item for the narrower remedy named below, not a rewrite of the subject set.

The thresholds are a proposal; the owner sets them. Their only job is to exist before the number does.

### Step 3 — record

On owner confirmation: add the ruling sentence beneath the stage-keyed-rigor clause in
`nonfunctional-requirements.md` as a recorded departure/clarification (not an edit to the clause itself),
comment the resolution on #771 and #180 item 3, and close issue #771 by hand
(`gh issue close 771 --reason completed`).

## Options considered and rejected

- **Make records full subjects again.** Reverses the shipped structure and the owner's escalation. Rejected.
- **Drop the Records Pass.** Loses the 23% BLOCKING class and the ships-a-falsehood window. Rejected; the
  tree records that a ceiling of WARNING "would have traded them away silently".
- **Reviewer-proposed record patches / composing over the judgeable projection.** The issue's scope-out
  names these as the two routes already sequenced after the termination plan. Not re-filed here.
- **Comment/docstring-only exemption for `.py`.** `is_judgeable_path`'s docstring records this was built
  and reverted (2026-07-29): `prawduct:allow` pragmas live in comments. Do not reopen without new evidence.

## Remedy if Step 2 fails

Smallest first, each testable against the Step 1 instrument:

1. Narrow the Records Pass bars (e.g. drop "misleads into action" to boundary-only).
2. Cap the Records Pass at NOTE at `final`, keep it at full severity at `cumulative` only.
3. Only then revisit what counts as a record prefix.

## Open questions for the owner

1. **Confirm the ruling wording** (§ The ruling), and that it may be recorded under the stage-keyed clause.
2. **Thresholds** in Step 2 (10% boundary, 5% inner): accept or set.
3. **Is Step 1 worth a chunk?** It is the only remaining work and is small. The alternative is closing #771
   on the ruling alone and accepting the post-fix cost as unmeasured; that leaves acceptance item 1 unmet.

## Risks

- **`files` is model-written.** The classification inherits the reviewer's choice of which files to name;
  the no-files share and a hand check of a sample of record-only rows are the guard.
- **Ledgers are per-worktree and gitignored.** The instrument sees only what a given machine recorded;
  the script must say how many repos and worktrees it read.
- **A low record share could mean reviewers learned to cite code files instead.** Cross-check against the
  disposition outcomes (#941) before reading a drop as a success.
