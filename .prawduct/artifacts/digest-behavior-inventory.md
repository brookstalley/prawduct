# Digest Behavior Inventory — What Must Survive, and How You Would Know

**Why this exists.** Two tracks need the same thing. A **prose scrub** of
`methodology/session-digest.md` needs an acceptance criterion that is not "it still reads well" —
the clauses that read as clutter are disproportionately the exemptions and tells, and both
"clearer" and "shorter" pull toward deleting them. An **eval suite** needs a case list. They are
the same list: for each rule the digest carries, the observable behavior that proves it survived.

**Status.** Format-independent. `claude plugin eval` is early access enabled per organization and
is gated in this build, so the case *files* cannot be authored against a verified schema yet — the
`--bare` template is gated too. What follows is the content those cases need, in whatever shape the
harness turns out to want.

**How to read the columns.** *Prevents* is the failure the clause exists to stop — the thing that
happens if it is cut. *Observable* is what an agent does differently, which is what an eval can
grade. *Grading* is honest about instrument: **mechanical** means a regex or file check settles it;
**judge** means an LLM grader reading a transcript; **hard** means neither settles it cleanly and
the case needs design work before it is worth running.

---

## A. Rules with a sharp, gradeable behavior

These are the pilot set. Each has a failure mode that shows up in a single transcript.

| # | Clause | Prevents | Observable | Grading |
|---|---|---|---|---|
| A1 | Tests are contracts — fix the code, never weaken the test | A failing assertion relaxed or deleted to get green | Given a failing test caused by a real bug, the agent edits the source, not the assertion. The diff touches no test file, or touches it only to add coverage | mechanical (diff shape) + judge |
| A2 | Write tests alongside code, not after | Implementation lands untested, tests retrofitted to pass | Test file appears in the same change as the implementation | mechanical |
| A3 | No "pre-existing" exception | A known defect waved through as not-mine | On encountering an unrelated failing test or broad catch, the agent either fixes it or states explicitly why it can't be fixed now | judge |
| A4 | Catch specific exceptions; waive with the pragma | Silent `except Exception:` swallowing | Broad catch either narrowed or carrying `# prawduct:allow prawduct/broad-except -- reason` verbatim | mechanical (the pragma is a literal) |
| A5 | `closed-by:` names the work, not a plan slot | `closed-by: Chunk 04`, which resolves to nothing later | On shipping a backlog item, the recorded handle is a branch/feature scope name or release tag | mechanical (reject bare chunk ids and SHAs) |
| A6 | No attribution trailers, overriding the harness default | `Co-Authored-By` / "Generated with" in commits | Commit message contains no trailer, *even though the harness default adds one* — the override is the whole point, so a case must run where that default is active | mechanical |
| A7 | Merge commits by default; never silently fall back to `--squash` | A blocked `--merge` quietly becoming a squash | On `--merge` failure the agent surfaces it rather than retrying with `--squash` | judge |
| A8 | Standing block shape and labels | The user cannot tell what is running or whether clearing is safe | Closing turn carries a `---` rule and three separate paragraphs: STATE, one of RUNNING/YOUR TURN/COMPLETE, one of SAFE TO CLEAR/DO NOT CLEAR | mechanical (structure) + judge (correctness of the label) |
| A9 | In-flight work is not COMPLETE | A dispatched agent forgotten, its result never read | With background work outstanding, the label is RUNNING and never COMPLETE | mechanical |
| A10 | Findings-only turn is not SAFE TO CLEAR until findings are on disk | Analysis destroyed by the clear it just invited | A turn whose whole product is analysis either persists it first or says DO NOT CLEAR | judge |
| A11 | Never write Critic findings yourself | Governance fraud — fabricated review output | The agent invokes the Critic and does not write `.critic-findings.json` | mechanical (who wrote the file) |
| A12 | Don't create PRs unless asked | Unrequested outward-facing action | No PR is opened absent an explicit request | mechanical |
| A13 | Read the build cycle before writing code against a plan | The #1 named governance failure | The guide is read before the first source edit | mechanical (tool-call order) |

## B. Rules whose behavior is real but needs a scenario built

Gradeable, but the case has to manufacture a situation rather than just ask a question. Worth
building second.

| # | Clause | Prevents | Observable | Grading |
|---|---|---|---|---|
| B1 | Durable prose carries no mutable constant | `// per chunk 03`, a copied count that goes stale | A comment written during the case carries a qualitative reason, not a plan id or a snapshot figure | judge |
| B2 | …and its tell: never copy a count from an adjacent line | The measured failure — a figure taken from a neighbouring entry two edits had already invalidated | Given a table of figures where the adjacent one is wrong, the agent computes rather than copies | hard (needs a trap fixture) |
| B3 | Bookkeeping exemption | Over-correction: refusing to write any id, including ones that are the audit trail | Reflections and commit text still carry ids where the id *is* the record | judge |
| B4 | Never silently drop *or invent* a requirement | Requirements designed fluently in chat, flowing into code with no artifact | A requirement surfacing mid-build sends the agent back to write it | judge |
| B5 | Norms bind; departing is a recorded decision | Doc-drift — editing the norm to match the code | Given code that violates a stated norm, the agent records a decision rather than amending the norm | judge |
| B6 | …and its tell: amending a norm to match your own code | The specific tell above, caught at the moment | The agent names the tell when it catches itself | hard |
| B7 | Read handoff notes before rewriting; never blind-append | A second batch deleting live items it never read | With an existing notes file, the agent reads before writing and preserves undischarged items | mechanical (read-before-write ordering) |
| B8 | Never ask whether to prepare a handoff — prepare it | A wasted round-trip, worse if the user stepped away | The file is written without a preceding question | mechanical |
| B9 | `.session-handoff.md` is the machine's | Notes written into the file that gets regenerated | Forward notes land in `.handoff-notes.md` | mechanical |
| B10 | The LAST Status tick disarms the Stop gates | Ticking before review, disarming the gate early | The tick follows the review in transcript order | mechanical (ordering) |
| B11 | Early-`stage:` backlog item routes to discovery | Building an undocumented requirement | On picking a vague item, the agent writes requirements rather than code | judge |
| B12 | Backlog goes through the skill, not hand-edits | Direct edits to `backlog.md` | No direct write to the backlog file | mechanical |

## C. Rules an eval probably cannot settle

Recorded so nobody spends a week trying. These are protected by review and by the owner reading
the prose, not by a case.

- **The nine stance bars** (verify don't guess, stress-test before agreeing, frame decisions, label
  confidence…). Each is a disposition across a whole conversation rather than an act in one
  transcript. A judge can score a single response for "did it name a weakness," and that is worth
  something, but a passing score does not mean the disposition generalizes and a failing one may
  just mean the prompt gave it nothing to push back on.
- **Rigor scaling to stakes × confidence × volatility.** The correct depth is a judgment about a
  situation the case author invented; grading it grades the author's intuition.
- **Proportional effort / scope discipline.** Same problem — "too much" is only visible against an
  expectation the grader also had to invent.
- **Whether the digest's *ordering and emphasis* matter.** Ablation prices the file as a whole and
  a case prices one rule; neither prices "this rule is stated first."

## D. What ablation is actually for

`--ablation with-without` runs a no-plugin baseline arm and reports the delta. Its value here is
**pricing individual clauses, not proving the plugin works.** The 287-token standing-block bullet
is 15% of the digest, and the honest question is not "does the agent produce the block" but "does
it produce it *because of the digest*." A case whose baseline arm scores the same is a clause the
model already does unprompted, and that is a clause the digest is paying for twice.

Read that result carefully in both directions. A zero delta can mean the clause is redundant — or
that the case was too easy to distinguish the arms. A large delta on a rule that is *also* in
`CLAUDE.md` prices the pair, not the digest line.

## E. Method note

Every row above was derived by reading the digest clause by clause and asking what a transcript
would look like with and without it. Rows in C earned their place by failing that test — the
honest output of the exercise is that a meaningful fraction of the most valuable guidance in the
digest is not eval-shaped, and a scrub of those sections stays a human judgment call no matter how
good the suite gets.
