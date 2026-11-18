# Critic: Cross-Checks

The reviewer-facing half of the review cycle, loaded by every `final`/`cumulative` reviewer: the
chunk `Type:` selector, the rule that a finding never names a destination, and the cross-checks
`chunk` mode skips. The builder's lifecycle (mode selection, dispositions, the census, the round
budget, the ledger) is `review-cycle.md`, which reviewers do not load.

## Per-Chunk Type Protocol Selector

Each chunk also declares `Type:` — a separate axis from `Critic mode:`; definitions and when to declare each value live in `methodology/planning.md` "Choosing a Chunk Type". The Critic reads both fields and selects protocol per the matrix below. A missing or unrecognized `Type:` is treated as `code` (full protocol, fail-closed) — the Critic refuses to honor an unknown Type.

| Chunk type | When to use | Goals 1 (Broken) | Goal 2 (Missing) | Goal 3 (Unintended) | Test-evidence check | Stop-hook Critic gate |
|---|---|---|---|---|---|---|
| `code` (default) | Code or behavior changes | full | full | full | required | fires |
| `doc-only` | Methodology / template / prose-only edits | prose only | requirement coverage of prose deliverables | scope discipline | skipped | fires unless session is empirically doc-only too (file-extension based) |
| `trivial` | Code change whose low risk the author can name in `**Trivial because:**` | full | full | full + **rationale-vs-diff fit** sub-check (Goal 3) | required | fires |
| `cleanup` | Branch hygiene, file moves, dead-code removal | structural-only (no broken refs) | requirement coverage | scope discipline; tolerate zero diff | skipped | fires |
| `designer-handoff` | Visual / token / design-asset handoff to a human designer | skipped | skipped | skipped | skipped | **skipped** |
| `cumulative-final` | Marker on the last chunk of a multi-chunk plan | marker only — the chunk's review is the one `/prawduct:critic cumulative` (commit first, then run it once; no separate `final`) | — | — | — | fires |

When chunk type is `designer-handoff` and the Critic is invoked anyway, output a single line: `Review skipped — Type: designer-handoff (visual handoff; review-by-human)` and exit clean — BEFORE `prawduct-hook critic-begin` (SKILL step 1), so no critic-active marker is left to block `clear`. No findings file is required; the stop-hook gate skip is the structural enforcement.

## A Finding Never Names a Destination

**Reviewers: never name the backlog as a finding's destination, at any severity.** Disposition is
the builder's call, made once with the whole diff in view; a reviewer-suggested destination
pre-empts it and reads as a licence to file without deciding. State
the defect and its consequence, say what a fix would take when that isn't obvious, and stop.

## Final-Mode Cross-Checks

After the goal-based review in `final` mode, run two additional passes that `chunk` mode skips — the Records Pass and the Governing-Artifact Reconciliation. **`final`/`cumulative` owns both.** Record-lint is not a pass of yours (below).

### A Written Rule With No Enforcer

**When a written rule has no enforcer, the finding is the rule — once.** It binds every reviewer role, and its canonical statement — the two conditions and the `rule-unenforced:` title prefix that keeps the yield countable — lives in `agents/critic-reviewer.md`. Coordinator roles get it as their brief; **single-pass, open it from here** — no `SKILL.md` protocol file carries it. When a finding rests on a `.claude/rules/learnings/` rule, quote that rule's opening words in the finding, so the citation is countable.

### Records Pass

**Records govern review SCOPE, not review READING.** A file plays two parts and only one narrows:
it can be *wrong* (**subject**), and it is what the code is judged *against* (**oracle**). Every spec
here is a record and Goal 2 and Goal 3 both need one in hand, both rating BLOCKING — so `critic-begin`
narrows `files_reviewed` to the **subjects** and hands what it sheds over as `files_oracle`, read and
not rated. **The subject test is its own question — *may a finding be about this file?* — and is NOT "is it
judgeable", which prices a round instead.** A deliverable, and prose that governs behaviour, are
subjects however the gate prices them; only a record *about* the work (`.prawduct/**`) is an oracle
(`coverage_algebra.is_review_subject`, whose docstring carries why the two must not be one). *"The code violates this spec"* has the **code** as
its subject; nothing here touches it.

**Two producers own oracle findings and are NOT narrowed** — the subject rule governs what a reviewer
*derives*, and every site that assigns a severity to an oracle target reads this sentence rather than
restating it: **record-lint**, which consolidation records at its own severities (`chunk-ref-missing`
BLOCKING included — the machine already answered and no mode may swallow that answer), and this
pass. Anything else you derive has a `files_reviewed` subject.

That leaves one window — a shipping falsehood in a record, unreviewed — and this pass is its cover.
At `final`/`cumulative` (`sustainability` under a coordinator roster), rate `files_oracle` against the
three bars and **name the set you covered**, so the exclusion is visible rather than silent:

- **It ships** — the inaccuracy reaches consumers as a false claim (release note, `CHANGELOG.md`, a
  published doc). *A change record asserting a guard that was never built → WARNING: a reader
  relies on a check that does not exist.*
- **It misleads into action** — an operator or agent following the record would do the wrong thing.
  *A measurement table assigning a probe a question it cannot answer → WARNING: the next operator
  runs it and records a fact it cannot produce.*
- **It must stop the merge** — an instruction that actively misleads (a wrong command, a deleted
  config reference) → **BLOCKING**, exactly as Goal 4 has always rated it. Making records oracle-only
  per round retired no severity: **54 of the store's 236 BLOCKING findings (23%) had a record as
  their only subject**, and this bar is where that class lands now. A ceiling of WARNING here would
  have traded them away silently.

**The bars decide WHETHER, Goal 4 decides WHICH — in that order, and this is its one home.** An
oracle record is a finding only once it clears a bar; then Goal 4's record severities assign which.
Read the other way round, its stale-artifact WARNING makes every out-of-date narration a finding —
the fix round this pass exists to stop buying.

Everything else — an imprecise count, a narration one revision short, a phrasing that could be truer —
clears no bar and is **not a finding**. Record-only findings were 36% of all findings across 728
measured reviews; the ones that clear a bar stay, and what this drops is the rest: correct, and not
worth what clearing one costs.

### Record-Lint — recorded by consolidation, never by you

`prawduct-hook critic-begin` runs deterministic record checks into the manifest's `record_lint`, and
`critic-consolidate` records every result and every `unchecked` entry in the review itself, at the
severity `record_lint.SEVERITY` assigns for the review's stage. **Never raise, restate, re-derive or
recount one** — your copy would be a second finding about the same record. Read them as context:
`chunks_graded`/`plan_graded` name whose deliverables were checked, and a `null` count is a check
that produced no answer, not a zero.

### Governing-Artifact Reconciliation

**The missing paperwork is record-lint's, not yours.** A governing norm with no disposition line, a
cited artifact that does not exist, or a frontmatter no parser can read is `governed-by-gap`, which
consolidation records — never raise it. What the lint cannot see is whether a recorded disposition
is **true**: a `conforms` (or `inapplicable because X`) over a diff that departs from the norm is a
departure without a recorded decision — the Authority Rule's territory, **BLOCKING** via Goal 3.
A plan with no `governed_by:` field in a product that already carries `## Direction` sections is an
observation recommending the `prawduct-hook jurisdiction` seed. Under the coordinator pattern this
pass is the `correctness` reviewer's, which holds Goal 3.
