# Issue #951 — telemetry: record `found_by` on bugs so review escapes are measurable: Requirements

`status: draft · stage: requirements · area: governance/telemetry · added: 2026-10-03 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/951`

Related: #948 (wave 1 `prawduct-hook stats`, the surface B5 joins), #949/#950 (contribution and
collection of stats; B5 flows through them only after it exists locally). Phase 2 of the program in
`.prawduct/artifacts/roi-audit-2026-10-02.md` (owner decision 2026-10-02: "Escapes (B5) are phase 2").
That artifact is not on `develop` at the time of writing; the issue body is the only copy of its
claims used here.

## Problem

Prawduct reports review *activity* (findings per review-hour, acted-on rate) but not review
*protection*: the defects a review let through. A bug found later by a user, a test, or a different
session is filed like any other bug, with no record that the change that caused it had been reviewed
and passed. "Blocking fixed per review-hour" therefore cannot distinguish a review that is effective
from one that is merely busy (audit finding 6, metric B5).

Two facts are missing, and both are needed:

1. **How the defect surfaced** (`found_by`) — recorded at intake, while the finder still knows.
2. **Which reviewed change introduced it** — so the bug can be counted as an escape *of that review*,
   and per plugin version.

## Users and the decision they make

- **Framework owner** — decides whether a review rigor change (stage-keyed rigor, reviewer model,
  proportionality) improved or degraded protection. Needs: escapes per plugin version, next to the
  wave-1 cost and yield numbers for the same version.
- **Builder/triage session** — files the bug; must be able to say how it surfaced in one token, with
  no investigation.

## Requirements

### R1 — `found_by` is recorded at bug intake

- A bug item carries `found_by`, a **closed** vocabulary: `review` (a Critic/PR review found it),
  `test` (a failing test or CI), `user` (a person using the product), `session` (a later agent
  session, unprompted by the above), `unknown`.
- It is a **block field with a `found-by:` label-free encoding** (data model §1.1, block evolution is
  additive-only — an item without it decodes as `unknown`, never as an error).
- It applies to `kind:bug` items only; setting it on other kinds is rejected, not ignored.
- It is accepted on `add` and settable once afterwards via `update` (the finder's answer can arrive
  after filing); changing a non-`unknown` value requires an explicit flag.
- The default at filing is `unknown`, and `unknown` is **counted and reported**, never folded into any
  other bucket — an absent answer must not read as "found by review".
- Upstream bug reports (`/prawduct:report-bug`) are out of scope for the payload: the outbound
  contract is a fixed field set, and `found_by` on the *upstream* copy would leak process detail.
  The local triage copy carries it.

### R2 — a bug can name the change that introduced it

- A bug carries an optional `introduced_in`: a commit SHA (or `unknown`). Set by whoever fixes or
  triages it, once the cause is known.
- `escape` is **derived, not stored**: a bug is an escape of review *R* when `introduced_in`
  resolves to a change whose tree (not just head SHA — squash and rebase rewrite SHAs) has a
  recorded passing review in the governance ledger. Storing the derived verdict would be a second,
  forgeable copy (data model §1.2 argument).
- A bug whose `introduced_in` has no recorded review is **not** an escape; it is counted separately
  as `unreviewed-origin`. A bug with `introduced_in: unknown` is `unattributed`. The three buckets
  sum to the bug count; `unattributed` is always shown.

### R3 — attribution method (resolves the issue's open requirement)

The issue leaves open: blame on the fix's lines, reviewer judgement, or an intake question. This
document **recommends a layered default, cheapest first, and leaves the first to be proven in design**:

| Method | Cost | Reliability | Use |
|---|---|---|---|
| **Blame on the fix's removed/changed lines** → candidate introducing commit(s) | none at filing; one git query at fix time | good for localized fixes; poor when the fix *adds* missing code (no lines to blame), or the bug is a spec/design omission | **Default**, computed when a fix lands, proposed to the fixer as `introduced_in` for confirmation |
| **Fixer's judgement** | one question at fix time | highest, but depends on the fixer being honest about their own prior work | The confirmation/override on the proposal; also the only path for add-only fixes |
| **Intake question** ("what change broke this?") | cost at the moment the finder knows least | low — the finder usually cannot answer | **Rejected** as the primary; `found_by` is the only intake question |

Constraints the method must satisfy (acceptance for design, not a design):

- The proposal is **advisory**: nothing blocks a fix on it, and a wrong or missing proposal degrades to
  `unattributed`, never to a false escape.
- Where blame returns several commits, attribute to the **latest reviewed one touching the removed
  lines** only if one is unambiguous; otherwise leave `unattributed`. Prefer an honest gap to a
  guessed escape — a false escape poisons the metric that justifies the review.

### R4 — attribution resolves to a review, per plugin version

- Given `introduced_in`, the stats reader finds the review event(s) for that change in the governance
  ledger (`review.critic` / `review.pr`) and attributes the escape to that review's **plugin
  major.minor**, the same key wave 1 groups by.
- **Known gap to resolve in design:** the ledger is gitignored and per-clone, and #948's comment records
  that ledger lines carry no plugin version (why B6 was descoped). B5 depends on the same attribution
  wave 1 used for its per-version numbers; design must state what that is and that it works for a
  review that ran in a different clone or an older session, or B5 inherits the B6 descope.

### R5 — `prawduct-hook stats` reports B5

- Per plugin major.minor: bugs fixed in the window, split `escape` / `unreviewed-origin` /
  `unattributed`, by `found_by`; and **escapes per review** for the versions' reviews.
- The report states the **attribution rate** (attributed ÷ all bugs) beside every escape number, so a
  low rate reads as "not measured" and not as "few escapes".
- `--json` gains the block under a schema-version bump per the existing contract
  (`plugin/docs/governance-telemetry.md`); the prose contract updates in the same change.

## Non-goals

- Building any of this before wave 1 ships (#948 merges) — owner decision; this item's design may
  proceed, build waits.
- Retroactive attribution of existing bugs. Existing items stay `unknown`/`unattributed`; no backfill
  job.
- Changing review gates or severity from escape data. B5 is measurement only.
- Contribution/collection of the metric (#949, #950) — B5 must exist locally first.

## Open questions

1. **Tree identity across history rewrite.** Which key makes "this change was reviewed" survive squash
   merge — the verdict cache's tree key (`lib/tree_key_memo.py`, `lib/verdict_cache.py`) or the
   ledger's `git.head`? Design must pick one and verify it against a squash-merged branch.
2. **Where `introduced_in` is proposed.** At `/prawduct:backlog` close of a `kind:bug`, in the fix PR
   flow, or by a `prawduct-hook` subcommand the fixer invokes? Requirement is only that it is
   proposed once, at fix time.
3. **Non-framework products.** Product repos run this on their own backlog; whether their ledger has
   enough history to attribute is an adoption question for #949, not a blocker here.

## Acceptance (from the issue, made checkable)

- [ ] `add`/`update` on a `kind:bug` accepts `found_by` from the closed vocabulary; any other value, or
      use on a non-bug, is rejected with a message naming the valid set.
- [ ] A bug filed without `found_by` decodes as `unknown` and appears as its own bucket in the report.
- [ ] Given a bug whose `introduced_in` change has a recorded review in the ledger, the report counts
      it as an escape of that review and per that review's plugin version; given one with no recorded
      review, as `unreviewed-origin`; given `unknown`, as `unattributed`. (Falsifying fixtures: all
      three, plus a squash-rewritten SHA that still resolves.)
- [ ] `prawduct-hook stats` (text and `--json`) shows B5 with the attribution rate beside it; the
      schema bump and `governance-telemetry.md` land together.
- [ ] A fix that only adds code (nothing to blame) yields no proposal and no false escape.
