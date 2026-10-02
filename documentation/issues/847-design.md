# Issue #847 — Critic: A Class Finding Gets Closed at the Instance It Named: Design

`status: draft · stage: design · area: governance · added: 2026-09-29 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/847`

Related: #640 (reporting-side half; closed), #694 (merged into this item: closure *property*, not a
grep), #167 (round count, the sibling attack on the same review-cost volume), #724 / the review-cost
investigation (`.prawduct/artifacts/review-cost-investigation-2026-09-19.md`, source of the 23% / 18%
figures — re-derive before quoting; the command is in its §6).

## Problem (restated)

A reviewer files a finding rated `class` and lists its members in prose. The builder fixes the
member the finding led with, `verify-resolutions` grades the *finding* fixed, and the next round
finds the members nobody touched. Nothing mechanical compares "members the finding listed" with
"members the resolution discharged". Success is: one round finds what three do now, without
raising severity or adding a blocking gate (the issue rules both out — the reviews already catch
every defect; the cost is rounds).

## What is already in the tree (verified 2026-09-29 — the issue's comments predate some of it)

The 2026-09-19 comment says `rule-unenforced` appears nowhere under `plugin/`. **That is no longer
true**: it now lives in `plugin/agents/critic-reviewer.md`, `plugin/skills/critic/cross-checks.md`
and `plugin/skills/pr/review-protocol.md`. So the reporting-side prerequisite has shipped and is not
this item's work. Re-derive with `grep -rn 'rule-unenforced' plugin/`.

Shipped and relevant:

- **Scope labelling.** `plugin/skills/critic/review-protocol.md` § Output Format asks every
  site-naming finding for `**Scope:** instance | class | none — <why it broke>`, and
  `FINDING_SCOPE_DIRECTIVE` (`plugin/lib/critic_consolidate.py`) delivers the same rule at `chunk`
  and `verify-resolutions` dispatch. `tests/test_finding_scope_rule.py` pins that every mode
  reaches it.
- **Grading rigour.** `RESOLUTION_IS_A_CLAIM_DIRECTIVE` already tells a verify reviewer to re-run a
  class finding's own reason as a search before writing `fixed`.
- **Roll-call.** `account_for_prior_blockers_directive` / `carried_blocking` make a verify pass
  give every prior *finding* a verdict.

What is **not** there — and is the whole gap:

1. `Scope:` is **prose inside `recommendation`**. The partial schema
   (`_validate_partial`: `{name, goal, severity, recommendation, files?}`) has no scope field and no
   member list, so nothing downstream can read either.
2. A resolution is `{review_id, fid, disposition, rationale?}` — one verdict per finding. There is
   nowhere to say "fixed members 1 and 2 of 4".
3. Every existing control is **advice at dispatch**. The core learning this issue quotes
   (*a rule you must recall is its weakest form*) applies to these directives too: they are recall.

## Design

Three additions, all optional and additive, so an old partial validates unchanged.

### D1 — Class findings carry members as data

Add optional fields to a finding in the partial schema:

```json
{"name": "...", "severity": "blocking", "recommendation": "...",
 "scope": "class",
 "closure": "<the property that defines membership, one sentence>",
 "members": [{"id": "m1", "site": "path or symbol", "note": "optional"}, ...]}
```

- `scope` is `instance | class | none`; absent means today's behaviour (nothing enforced).
- `closure` is #694's ask, folded in: the **property** that decides membership, with any grep
  offered only as a hint. It is the resolver's target and the verifier's test.
- `members` is the enumeration the reviewer already writes in prose. `id`s are reviewer-local and
  stable within the finding (`m1..mN`); the fact stores them verbatim.
- Validation is **tolerant, not fail-closed** (per the learning on model-written fields): a class
  finding with no `members` is accepted and simply gets no member grading. A malformed `members`
  entry is dropped with a warning, never a refusal of the whole consolidation.
- `scope: class` with `members` absent is the reviewer saying "I cannot bound it" — record that
  as-is; it is information (see D3).

The reviewer's cost is small: it writes a list it was already writing as a sentence. The directive
`FINDING_SCOPE_DIRECTIVE` gains one clause pointing at the fields; prose instructions stay the
carrier of *what to write*, the schema becomes the carrier of *what is checked*.

### D2 — Resolutions grade members

Extend a resolution entry with an optional `members` array:

```json
{"review_id": "...", "fid": "R-3", "disposition": "fixed",
 "members": [{"id": "m1", "disposition": "fixed", "evidence": "..."},
             {"id": "m2", "disposition": "waived", "rationale": "..."}]}
```

Consolidation rule for a `fixed` resolution whose target finding has recorded members:

| Members covered by the resolution | Outcome |
|---|---|
| all ids present, each `fixed` (with `evidence`) or `waived` (with `rationale`) | resolution recorded as today |
| some ids missing | resolution is **recorded as partial**: the finding is *not* lifted out of `unresolved_blocking`; the consolidate `NEXT-ACTION` names the missing member ids |
| target finding has no members (old finding, or class with no list) | today's behaviour, unchanged |

"Partial" reuses the existing rule that omitting a finding from `resolutions` keeps it blocking
(`RESOLUTION_IS_A_CLAIM_DIRECTIVE`: omission fails closed). The new state is *the same fail-closed
answer, reached with more information* — the reviewer is told which members are outstanding instead
of the builder discovering them next round. It is deliberately **not** a new severity, not a new
gate, and not a new refusal: the gate's inputs (`unresolved_blocking`) are unchanged in kind.

`waived` members require a rationale, mirroring the finding-level rule (R7).

### D3 — Dispatch hands the verifier the member list

`account_for_prior_blockers_directive` already lists prior blocking findings by id at verify
dispatch. Extend each line with its `closure` and `members` when recorded, so the roll-call is
per-member. This is the *before* half; D2 is the *after* half — the same two-times pattern that
directive's docstring already describes for finding-level roll-call.

A class finding whose `members` is absent renders as "class, unbounded — closes only by a
construction" in that roll-call, which makes an unbounded class visible to the builder at the moment
of fixing rather than after.

## Alternatives considered

- **Parse the member list out of prose.** Rejected for the reason `carried_blocking` gives: the
  phrasings are an open set, so a parser that misses one fails in the same silent direction as the
  bug.
- **A new blocking gate over class findings.** Rejected — the issue says not to, and the data show
  no missed defects. D2 changes only what a `fixed` claim is allowed to *lift*.
- **Raise class findings' severity.** Same rejection; it costs rounds, which is the thing being cut.
- **Build the resolution symmetry as `rule-unenforced`-style title conventions.** That convention
  reports a rule once; it says nothing about how a resolver discharges a member set.
- **Only strengthen the directive prose.** It exists twice already (`FINDING_SCOPE_DIRECTIVE`,
  `RESOLUTION_IS_A_CLAIM_DIRECTIVE`) and the three-round incident happened with the rule quoted back
  correctly. More recall is the failing carrier.

## Risks and open questions

1. **Unbounded classes.** The hardest class findings are the ones whose reviewer *cannot*
   enumerate. D1 records that honestly, and the existing construction rule ("one owner every member
   passes through") remains the only closure. This design does not solve them; it stops the
   *enumerable* ones being closed early. Sizing that split needs the ledger (see Measurement).
2. **Reviewer-invented members.** A reviewer could pad `members` and force needless work.
   Mitigation: `waived` with rationale is always available, and the verify pass is itself a
   reviewer that can write it.
3. **Does a partial resolution cost a round?** Under D2 a builder who fixes 2 of 4 members and
   claims `fixed` now learns at consolidation (same round) rather than next round. The design
   should be net-negative on rounds only if reviewers *do* list members; if adoption is low it is
   inert. Decision needed: is inert-on-low-adoption acceptable, or should the reviewer directive
   make `members` mandatory for `class` (which conflicts with risk 1)? Recommendation: keep it
   optional, measure adoption, revisit.
4. **Schema versioning.** New optional keys on facts: check `data-model.md` and the fact reader
   for a strict-key policy before building. A writer/reader mismatch across plugin versions
   (pins are per-project and lazy) must degrade to today's behaviour — an old consolidator seeing
   `members` must ignore it. Verify by test, not by reading.
5. **Where the closure property is evaluated (#694's acceptance).** Proposed answer: the *finding
   author* records it (D1), the *resolver* addresses it per member (D2), and the *verifier*
   grades each member against the `closure` sentence (D3 + existing grading directive).
   `verify-resolutions` remains the only place resolution facts are minted (data-model rule).

## Measurement (before building)

Per the learning "a filed item's stated mechanism is a hypothesis": before implementation, from
`.prawduct/.governance-ledger.jsonl` and the evidence store, measure over post-2026-08-04 reviews
only (the era split that invalidated other pooled figures in this program):

- share of `class`-rated findings whose recommendation prose enumerates ≥2 members (the D1
  addressable set);
- of those, how many were later followed by a same-`scope=` blocking finding naming a member they
  listed (the D2 catch rate — the number that justifies the work);
- confirm 943/4,084 and 95/533 reproduce, and record the command, not the digits.

If the D2 catch rate is under a handful per month, stop after D1+D3 (visibility only).

## Build sketch (for the eventual plan; not a plan)

1. `_validate_partial` + `merge_findings`: accept and persist `scope`, `closure`, `members`
   (tolerant). Tests: old partial unchanged; malformed member dropped, not refused.
2. Resolution schema + consolidation: partial-coverage state; `NEXT-ACTION` names missing ids.
   Tests must be red-verified against the pre-change source, including a `fixed` covering 2 of 3.
3. `account_for_prior_blockers_directive`: per-member roll-call; pin the rendered branches
   (members present / class unbounded / instance).
4. Directive + `review-protocol.md` + `critic-reviewer.md` prose, then update
   `data-model.md`; check the always-injected digest character budget if the digest is touched.
5. Enumerate sibling surfaces performing the same act (the PR reviewer's finding path,
   `plugin/skills/pr/review-protocol.md`) — grep, do not recall.

## Scope-out

Severity changes; new gates; retroactive member extraction from old findings; the closed-#640
bookkeeping (owner's call, already noted on the issue).
