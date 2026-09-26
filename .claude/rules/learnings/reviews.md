---
paths:
  - "plugin/skills/critic/**"
  - "plugin/agents/**"
---
# Learnings — reviews

Rules that fire while running or acting on a Critic review. **Reading a rule is not applying it.** Name the rule and say what it changes about the decision in front of you, or say that it does not apply.

- A fix ships TWO artifacts that can each be false: the change and its evidence (a test blind to the bug, a comment its own assertion disproves). Sweep the NEIGHBOURING PROSE and tests in the same pass
- A background agent's liveness is answered by ITS OWN completion signal, never by reading files it is mid-write — a death verdict from a listing is how a re-dispatch clobbers a live review
- A finding "A is pinned, B is not" is discharged by PINNING B, never changing B. Generally, a fix commit carries the cheap check closing the loop it opens (test beside moved behaviour, parser run on a hand-authored record)
- A review ending is not a filing event: dispose each non-blocking finding FIX or ACCEPT; FILE only if it names a trigger, is chunk-sized, and can't be absorbed. Deep context on a small BLOCKER means fix it (review-cycle.md)
- Deferring to a live/operator check: SPLIT "can this be true in principle" (static — test now) from "does the harness do it" (live — queue). Bundling defers the testable half, where the bug usually is (CRT-2J8N matcher)
- A deferral queue whose enforcing gate is disabled is WRITE-ONLY — check the gate is ON when you defer into it; the deferral feels like diligence (operator-verification entries sat pending behind `operator_verification_required: false`)
- When a decision defers a SET of findings, reconcile the set against the filings before calling it done — nothing matches the lists automatically ("file all ten" produced six items covering eight)
- If `check-cumulative-critic` reports `uncovered` on reviewed code, suspect a stale base before a fresh review — the gate anchors to `origin/<base>`, so unpushed integration commits drag shipped work into the span
- Verify a review artifact's cited gaps against HEAD first — its claims aged when written. A `file:line` you didn't resolve is a claim, not a citation; anchor on symbols and headings, since stale digits never visibly break
- If the session switched branches after SessionStart, pass the Critic mode explicitly — `infer-critic-mode` trusts the stale session-start branch marker
- A review finding is about a CLAIM, not a file — resolve it by grepping the claim's wording everywhere it appears, and never truncate the recommendation you are acting on. Tell: you fixed the one file the finding cited
- A latent defect judged 'harmless' or 'inert' is harmless only for now — name the condition keeping it dormant and check whether your changeset (or the next feature touching that path) removes it before deferring or relying on the verdict
- After a clean cumulative (0 blocking/0 warning), NOTEs are advisory — don't chase cosmetic ones: fixing them reopens the coverage gate on judgeable governance files and forces a no-value review pass
- When a fresh-eyes reviewer's claim about a project CONVENTION (release timing, bookkeeping) conflicts with a durable learning + the process doc, the documented convention wins — the reviewer read only the current tree; re-verify before acting
- A reviewer's NOTE/severity is a prior, not a verdict — before calling a change to a gate input harmless, grep the value's READERS; its comment block says what it's for, not who consumes it (nulling `active_build_plan` silently disarmed two gates)
- An agent's `tools:` binds by TOOL (no `Bash` entry = no Bash, measured); `Bash(pattern)` narrowing is declared, unverified. Make the tool SET the safety boundary; never call a pattern 'structurally enforced' without watching the harness refuse
- Reactive checks (tests, Critic, reviews) validate what EXISTS and cannot see what is missing — completeness auditing is a separate act: periodically ask 'what should exist here that doesn't?', not only 'is what exists correct?'
- Expect a cumulative Critic to find >=1 regression chunk reviews missed — a mechanism from chunk N misbehaves against prose from chunk M, visible only across the span. Plan a remediation slot before `/prawduct:pr create`
- Test-evidence freshness is the `test-status` exit code ONLY — never a commit/SHA field (`git_sha` retired as misleading). What it composes has grown (session timestamp, tree-validity clause, `degraded` flag): read the gate, not a remembered rule
- Before filing a finding against a mechanism, read that mechanism's own documented degradations — a design that enumerates its deliberate weaknesses has usually already considered yours
- Reads as evidence, is not: an absence-claim on a path that doesn't RESOLVE; a disposition recorded from intent, not the diff; a commit crediting a backlog item by title while its repro still reproduces; a subagent's count or list (a lead).
- A self-authored adversarial pass inherits the author's blind spots — the attacks you think of come from the model that wrote the code. Get the adversarial read from a context that didn't write the subject, or from a roster you didn't author.
- A disposition claiming 'fixed' must restate the FINDING'S OWN predicate and show it false — arguing from what the change found is satisfiable by fixing an adjacent surface. Tell: the fix note says what the fix caught, not what the finding said.
- Reviewer severity is a SCHEDULING decision — BLOCKING means 'the tree must not move again without this', so a record gap that can ride a commit already owed is an observation; rating it BLOCKING spends a whole round on a one-row edit.
- A negative repro that seems to CLEAR a finding proves nothing until the mechanism is shown live — fail-open code says 'fine' when inputs break. First run a case that MUST trip it in the same fixture. Tell: repro exits 0; about to overrule review.
- Scrub the WHOLE diff (tests and comments too) before dispatching a review, and scrub a grep-able ban BY GREP — a rule you just wrote you are still violating elsewhere; a reviewer's list is a sample, not a census. Tell: you scrubbed by re-reading
- Calling a prior fix "the same family" IS a class finding — recurrence says the first fix was scoped too narrowly; build the construction preventing both, over every site the shared predicate reaches. Tell: you cite a precedent, touch fewer sites
- When a fix is driven by a report's SUMMARY LIST, re-open the underlying scan — a deduping summary undercounts sites (4 advisory rows hid 5 Direction entries). Tell: your remedy's count equals the report's row count and you never opened the scan
- A refusal's REPLACEMENT route is judged by properties, not name: its span can be narrower than the one refused, and its cost is the next gate met (#167 saved 5 min, cost 12). Weak evidence stays advice. Tell: "re-dispatch" without saying as what
- When a control narrows what a REVIEWER sees, say whether it narrows the SUBJECT or the ORACLE (the specs code is judged against) — dropping the oracle looks like the narrowing working. Assert the oracle was DELIVERED, never that finding counts fell
- Check WHICH interval a Critic mode reviews: `chunk` ends at the working tree and starts at the manifest's base (`working_tree_interval_base`), not HEAD; `cumulative` = a commit range, so NOT committing misses your work. Tell: mode from the plan
- Before withholding a fix to protect a review round, run `cost-of-commit` (no args when the fix is all that's uncommitted) — docs, artifacts and .prawduct/ price `free`. Tell: you are reasoning about which paths move coverage instead of asking
- While a Critic review is LIVE, only read reviewed files; edit only free surfaces (.prawduct/, plan, change-log) — critic-begin snapshots the tree. Tell: test-status still exits 0; since #767 it NAMES the changed paths, but exit 0 is not permission
- A CLASS fixed at a SUBSET is worse than left alone — the partial repair removes the symptom that makes readers look and can leave prose arguing FOR the defect. Re-run the finding's falsifying query; fix every hit or accept. Tell: fix sized by rows
- Before recommending something be BUILT, check whether it was built and REMOVED — a removal comment is a measured decision (dangling-ref: 3 findings, 0 true); reopen only on new evidence. Tell: you propose a control without opening its host module
