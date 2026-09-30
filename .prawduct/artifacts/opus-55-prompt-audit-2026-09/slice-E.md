# Slice E: plugin/docs/ reference docs (all except principles.md)

## Inventory

Every file below was read in full, start to finish.

| File | Words |
|---|---|
| `plugin/docs/discipline.md` | 638 |
| `plugin/docs/doctor-vs-janitor.md` | 619 |
| `plugin/docs/governance-telemetry.md` | 2,266 |
| `plugin/docs/norms.md` | 4,661 |
| `plugin/docs/runbook-authoring.md` | 16,670 |
| `plugin/docs/test-report-contract.md` | 2,602 |
| `plugin/docs/waivers.md` | 1,371 |
| `plugin/docs/examples/observability-api-service.md` | 309 |
| `plugin/docs/examples/observability-event-driven.md` | 331 |
| **Total** | **29,467** |

I found no token or size ceilings on these files in `tests/`, so no budget needs lowering. Tests do parse some of the text, and those decisions are marked `machine_read: yes`:
- `tests/test_discipline_table.py` reads the `discipline.md` table: 6 cells per row, a numeric first cell, the Channel cell regex, and the anchors.
- `tests/test_test_report_contract.py` reads the Field table, the Condition table, the one JSON block, and every Python block (AST-parsed) in `test-report-contract.md`.
- `tests/preferences/test_registry_completeness.py` reads the `## The \`prawduct/*\` vocabulary` table in `waivers.md`.
- `tests/test_learning_events.py` pins the phrase "reads here as never fired" in `governance-telemetry.md`.

## Summary

The highest-impact decision is E-1. `runbook-authoring.md` calls length "the single most strongly evidenced finding in the entire literature", but its own invariant 4 says no experiment manipulated length and quotes the sources' hedges. It then names a *different* rule as "the most strongly evidenced". The runbook skill and template copied the overstated version. This is the modality drift the guide's own appendix warns about, copied to three files.

The second is E-4. `norms.md`'s enforcement table restates the BLOCKING severity as "where ratified norms exist", while its § Severity scopes BLOCKING to *adopted* norms, and § Adoption says ratification "records it, never creates it". The two Critic goal files copied the "ratified" wording.

The rest fall into three groups:
- **Builder self-verification.** A three-pass self-review in `runbook-authoring.md`, where only the subtraction pass is worth keeping as a length control.
- **Incident and version history inside instructions.** In `norms.md`, `waivers.md`, `governance-telemetry.md`, `discipline.md`, and the runbook evidence appendix.
- **Clauses addressed to the wrong reader.** Prawduct-internal norm and test references aimed at a consumer in `test-report-contract.md`, and a maintainer's correctness proof in `norms.md`.

`doctor-vs-janitor.md` and both `examples/` files are clean.

Counts: 19 decisions, 4 high and 15 medium. By action: rewrite 19 (several include deleting sentences or a section inside the rewrite), remove 0, move 0, add 0, flag 0.

## Decisions

### E-1: Length claimed as "the single most strongly evidenced finding", contradicting invariant 4 and invariant 1
- location: `plugin/docs/runbook-authoring.md:48-55`
- evidence: "single most strongly evidenced finding in the entire literature below:"
- pattern: #342 duplicated fact, drifting (internal contradiction, plus copies in two other files); 1a superlative inflation. Also hedge-hardening: the blockquote drops the "may be" and "carries the risk" that §4 (lines 529-534) says are the sources' own hedges.
- why: Line 388 names invariant 1 as "the most strongly evidenced rule in the entire literature", and lines 529-531 concede that "No experiment manipulated procedure length". Opus 5.5 follows instructions literally, so it will either reconcile the two claims or repeat the stronger one. The skill and template already repeat it.
- confidence: high
- action: rewrite
- replacement: Replace lines 48-55 with:
  "If you apply everything here to every procedure, you will produce a thorough, exhaustively cross-referenced document that **no tired human will read**, which is a failure that looks like success. The sources agree on the direction:

  > As a list grows there may be a higher probability of overlooking any given item, and length carries the risk that operators skip the procedure or execute it poorly ✓. Observed crews facing a long checklist degraded it into a hurried read-through, losing the redundancy it existed to provide."
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/runbook/SKILL.md:34` ("the best-evidenced finding in the whole literature"); `plugin/templates/runbook.md:33` ("Length is the best-evidenced defect in the whole literature")

### E-2: Scope-record reader table says "exactly as before the contract existed"
- location: `plugin/docs/test-report-contract.md:87`
- evidence: "exactly as before the contract existed. A repo that has not wired a producer is unaffected."
- pattern: 1d migration-relative phrasing
- why: The phrase is a diff against a version of the reader the model never saw. It implies there was an earlier behaviour to compare against. The next sentence already states the rule.
- confidence: high
- action: rewrite
- replacement: Change the verdict cell to: "**Proceed.** A repo that has not wired a producer is unaffected."
- model_dependent: no
- machine_read: yes. `test_the_readers_rules_keep_both_directions` requires the "No record" row's verdict to contain `Proceed`, and the replacement keeps it.

### E-3: Rulings paragraph narrates where rulings "used to live"
- location: `plugin/docs/norms.md:108-110`
- evidence: "case law belongs beside the statute it reads. It used to live in the learnings"
- pattern: 1d migration-relative phrasing; Group 2 history narrative
- why: This is the definitions home, so it should state the current rule as the only rule. "It used to live in the learnings rules" sends the model toward a location that no longer applies.
- confidence: high
- action: rewrite
- replacement: "Rulings live with the norm they rule on, in its `Rulings:` field: a `[[name]]` plus the ruling's statement. Norms are statute and rulings are case law, and case law belongs beside the statute it reads. A ruling is a record a reader consults, not a rule every session carries."
- model_dependent: no
- machine_read: no

### E-4: Enforcement table restates the severity with a different threshold ("ratified" versus "adopted")
- location: `plugin/docs/norms.md:314`
- evidence: "where ratified norms exist; NOTE in a norm-less product — see Severity above; PR reviewer: WARNING at its layer"
- pattern: #342 duplicated fact, drifting
- why: § Severity (lines 23-38) scopes BLOCKING to products that have *adopted* norms. That means any Direction section, any preferences norm row, or any recorded classification. § Adoption (line 382) says "ratification records it, never creates it". The table's "ratified" is narrower, and the two Critic goal files copied it. A reviewer reading only the Critic copy could downgrade to NOTE on a product that has a hand-written Direction section it never ran through ratification. § Severity already says it is "stated once", so the table should only point to it.
- confidence: high
- action: rewrite
- replacement: Change the Review row's third cell to: "departure without a recorded decision (severity by layer: § Severity above); the amend tell incl. doc-only; flip follow-ups present; norm-staleness signals (→ NOTE recommending `/prawduct:doctor`). The Critic considers jurisdiction independently — `governed_by:` is an input, not a boundary."
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/critic/review-protocol.md:43`, `plugin/skills/critic/goals-1-3.md:41-42` (both say "where ratified norms exist"). The home is `norms.md` § Severity.

### E-5: Three-pass self-review ritual aimed at the author
- location: `plugin/docs/runbook-authoring.md:37-39, 1401, 1498-1500`
- evidence: "Run this against your own draft before calling it done: six restraint checks, then 26 criteria."
- pattern: Opus 5 "Self-check instructions" and "Over-verification"; prawduct pattern "self-verification prose aimed at the builder"
- why: The guide asks the author to make three separate re-reads of its own draft: the subtraction pass, then 32 criteria, then "Read your draft once as each" of four postures. The runbook skill's Step 5 asks for them again. Opus 5-class models verify their own work unprompted, and explicit re-check instructions cause over-verification. The criteria themselves are the quality bar, and `/prawduct:runbook review` uses them as its rubric, so they stay; only the instruction to run them as extra passes goes. The **subtraction pass (lines 76-97) stays**, because it counters Opus 5's documented longer written deliverables and is not a correctness re-check.
- confidence: medium
- action: rewrite
- replacement:
  - Lines 37-39: "The [rejection criteria](#self-review--rejection-criteria) are the bar a finished runbook meets. If you are short on time, the two rules that recover most of the value are: **every verification step names an observed value**, and **every command is derived from the repository**."
  - Line 1401: "These are the bar a finished runbook meets, and the rubric `/prawduct:runbook review` applies: six restraint checks, then 26 criteria."
  - Lines 1498-1501: "**Four readers, one document.** A finished runbook serves all four, and they fail it in different directions. None of them is curious: every one is trying to get work done." (This deletes "Read your draft once as each.")
- model_dependent: yes
- machine_read: no

### E-6: Superlative inflation, with six "most" or "highest" claims competing
- location: `plugin/docs/runbook-authoring.md:336, 388-390, 1067-1068, 1204, 1250`
- evidence: "**This is the highest-leverage rule in this guide.**"
- pattern: 1a pressure language (emphasis without new information); 1c padding
- why: The guide already ranks its rules once, in "What is actually non-negotiable" (lines 99-108). The extra superlatives disagree with each other: "most actionable", "most strongly evidenced", "most commonly omitted", "most important negative result", and "highest-leverage". When every section is the most important, the markers stop carrying information. Several are also unsourced.
- confidence: medium
- action: rewrite
- replacement: Keep the ranking in lines 99-108 and cut the superlatives elsewhere. Worked examples:
  - Line 336: "This is the most actionable finding here, and it produces a hard rule:" → "It produces a hard rule:"
  - Lines 388-390: → "This rule is well-evidenced ✓ and converges from two independent directions: aviation human factors, and the largest empirical study of real software runbooks."
  - Lines 1067-1068: "This is the most commonly omitted section in software runbooks, and it is mandatory in the mature standards ○." → "The mature standards make this section mandatory ○."
  - Line 1204: "This is the most important negative result in the procedure literature, and the lesson transfers exactly:" → "The lesson transfers exactly:"
  - Line 1250: (delete)
- model_dependent: no
- machine_read: no

### E-7: Three overlapping step-classification rules, plus dated and volatile claims
- location: `plugin/docs/runbook-authoring.md:1358-1388` (overlaps `:1061-1063`)
- evidence: "each step as agent-safe or human-required. A step that is destructive, irreversible, or"
- pattern: 1c padding (the same rule stated three ways); Group 2 volatile specifics
- why: The guide asks the author to classify every step three times:
  - critical or irreversible (line 1061);
  - observe/act plus reversible/irreversible (line 1372);
  - agent-safe or human-required (line 1385).

  The three have slightly different criteria. The section also makes two claims that will go stale: "Anthropic's own agent harness implements this as a default-deny architecture", and "On the current SRE incident-diagnosis benchmark, no frontier model reaches 50%". Neither changes what the author writes.
- confidence: medium
- action: rewrite
- replacement: Replace lines 1358-1388 (both "Gate steps by reversibility" and "Know the ceiling on autonomous execution") with:
  "### Gate steps by reversibility, not by difficulty

  An agent executing a procedure produces rationale that may be confabulated ○, so go/no-go thresholds and the abort path are **written before execution**, not judged at runtime by the thing executing.

  > **Rule.** Split every procedure into an **observe** phase (read-only: inspect, query, measure) and an **act** phase (state-changing), and complete the observe phase first. Mark each act step reversible or irreversible, using the critical-step test in [Branching](#branching-and-steps-that-cannot-be-undone). Reversible steps may run and be logged for after-the-fact review. Irreversible, destructive, or user-visible steps require explicit human authorization before they run, an assumption a product may relax deliberately and in writing, never silently. Anything unrecognized fails closed to a human."
- model_dependent: no
- machine_read: no

### E-8: Model-hallucination statistics with pinned model names and dated rates
- location: `plugin/docs/runbook-authoring.md:1252-1264, 1338-1356`
- evidence: "On a low-frequency API benchmark, GPT-4o produced only"
- pattern: Group 2 volatile specifics and pinned model names; history narrative
- why: The rule ("derive, do not generate") and its reason stay. The four-row percentage table and the "2026 replication across five frontier models" figures go stale with every model release, and they name retired models. The actionable content is two sentences. The runbook skill copies the 4.6–6.1% figure.
- confidence: medium
- action: rewrite
- replacement:
  - Lines 1252-1264: "Models emit references to packages, flags, and endpoints that do not exist, at measured rates well above zero ✓, and cross-model agreement is not an existence check. An agent that generates an operational command on the fly instead of invoking a stored exact template drifts from the template, silently drops sub-conditions, and makes syntax errors ✓."
  - Lines 1338-1356: "### Name every target

    **Ambiguity in a procedure does not produce a question from an agent; it produces an invented answer** ○. Name the target of every state-changing step unambiguously: which host, which namespace, which cluster, which table. Writing the correct current syntax into the procedure is necessary but not sufficient, because memorized older syntax leaks through even with the current spec in context ○. That is the argument for deriving from the repo and for rehearsal, not for trying harder to remember."
- model_dependent: no
- machine_read: no
- dup_of: `plugin/skills/runbook/SKILL.md:67` (the "4.6–6.1%" copy)

### E-9: Evidence appendix narrates the guide's own research history
- location: `plugin/docs/runbook-authoring.md:1576-1578, 1580-1610` (and `:785-786`)
- evidence: "Two of those corrections were live defects in an earlier draft of this very guide."
- pattern: Group 2 history narrative; incident archaeology
- why: "An earlier draft of this very guide", "was cut off before its adversarial challenge phase ran", "its web search budget exhausted", and "resume instructions" tell the story of how the guide was researched. They do not change how a runbook is written or cited. The pointer to `.prawduct/research/.../CHECKPOINT.md` names a file the section itself says is not shipped. Keep the ○ caveat, the source list, and the "genuinely unaddressed" list.
- confidence: medium
- action: rewrite
- replacement:
  - Lines 1576-1578: (delete)
  - Lines 785-786: "One honesty note about that pedigree, because it is easy to overstate: NUREG-0899 is **guidance, not regulation**."
  - Lines 1580-1610: "### Sourced but not adversarially challenged ○

    Findings marked ○ are quoted from primary documents (OSHA 29 CFR 1910.147, MIL-STD-40051-2A, S1000D Issue 5.0, NIST SP 800-193, RFC 9019, DOE-HDBK-1028-2009, FAA AC 120-71B, NASA/TM-2014-218382, WCAG 2.2, official postmortems from AWS/GitLab/Cloudflare/Atlassian, the SEC order on Knight Capital, TSB A98H0003, the CSB Texas City report, and the Deepwater Horizon commission report) but were not put through adversarial challenge. The challenged set was corrected about half the time, almost always by softening overstated modality, so read ○ findings as directionally sound and probably stated a little too strongly. Check the source before quoting one as a mandate.

    Genuinely unaddressed: regulated-environment procedure requirements (FDA/GxP, ISO 13485), a systematic treatment of machine-vs-human documentation audiences, and any empirical evidence that a particular runbook *field set* improves outcomes. That last one appears to be convention everywhere, including here."
- model_dependent: no
- machine_read: no

### E-10: A maintainer's correctness proof inside the norms definitions home
- location: `plugin/docs/norms.md:323-352`
- evidence: "So the guarantee is proportionality (a fresh product never gets three simultaneous nags), not a hard"
- pattern: 1c over-specification; Group 2 "verbose, explaining what the reader cannot act on"
- why: About 450 words argue that probe layers 0, 1 and 2 are mutually exclusive, citing `lib/coverage_probes.structural_characteristics_recorded`. The reader is a model working on Direction sections. It needs to know what each layer asks and that layers 1 and 2 can both speak. It does not need the proof, which belongs in the probe's docstring and tests. The table stays.
- confidence: medium
- action: rewrite
- replacement: Replace lines 323-331 with:
  "**Structural-coverage staging.** The structural-presence hooks form a three-layer chain that stages a product from \"we don't yet know what this is\" to \"its norms are ratified\", so a fresh product never gets three simultaneous nags:"

  Keep the table (lines 332-336). Replace lines 338-352 with:
  "Layers 0 and 1 key off one predicate, whether `classification.structural` records at least one characteristic, so they never fire together. Both stay silent on a freshly-onboarded empty repo, which `coverage-status` shows as the chain not yet engaged. Layer 2 has its own gate: it fires once any strategy-class artifact exists and the registry is unratified. During partial authoring, layers 1 and 2 can therefore both speak, as two distinct asks."
- model_dependent: no
- machine_read: no (`tests/test_coverage_probes.py:600` cites the section in a comment only)

### E-11: Stopgap field explained through the defects that produced it
- location: `plugin/docs/norms.md:255-264`
- evidence: "Both halves of that shape are load-bearing, and each is a defect this spec has already paid for"
- pattern: Group 2 history narrative
- why: The parser constraints are worth keeping: a single-word label, and a parseable `expires <date>`. The framing "each is a defect this spec has already paid for once", with a replay of the `Live exception:` failure, is incident story.
- confidence: medium
- action: rewrite
- replacement: "Both halves are load-bearing. The label is **one word** because the entry parser treats only single-word capitalized labels as line starts; a multi-word label soft-wraps into the field above, where no matcher sees it and its backlog citations are read as that field's. The `expires <date>` bound is **the whole field**. The stall advisory stays quiet for a stopgap whose expiry is still ahead and fires once it passes, independently of the stall clock, since touching the tracking item resets that clock. A `Stopgap:` with no parseable expiry suppresses nothing, and an exception with no clock is not bounded."
- model_dependent: no
- machine_read: yes. The prose describes a parsed field; the `Stopgap:` example block (lines 250-253) and the format it states do not change.

### E-12: Stall window described as "fixed today", and elsewhere as a "default"
- location: `plugin/docs/norms.md:243-245, 373`
- evidence: "for the 30-day stall window raises an advisory (a fixed window today; a config surface is"
- pattern: 1d time-relative phrasing; #342 drift (line 373 says "30-day default", which implies it can be configured)
- why: "Today", and "deferred until any probe needs one", are roadmap notes. Line 373's "default" contradicts "fixed". `lib/norm_probes.py:146` records that the spec once said "configurable".
- confidence: medium
- action: rewrite
- replacement:
  - Lines 243-245: "…Stall detection is mechanical: the tracking item's backlog entry unedited (no status, stage, or content change) for 30 days raises an advisory."
  - Line 373 cell: "Transitions — interim rule; stall advisory (30 days); stopgap = bounded exception"
- model_dependent: no
- machine_read: no

### E-13: "No prose-parsing probes" argued from a hook's history
- location: `plugin/docs/norms.md:428-429`
- evidence: "The orphan-term hook's noise history is the cautionary tale: a"
- pattern: Group 2 history narrative
- why: The rule's authority is the behaviour it prescribes. The orphan-term hook is not something the reader can look up.
- confidence: medium
- action: rewrite
- replacement: "- **No prose-parsing probes.** A probe that misfires trains its reader to ignore the one real catch."
- model_dependent: no
- machine_read: no (only test docstrings paraphrase this sentence)

### E-14: Waiver design argued against the design it replaced, contradicting the registry sentence
- location: `plugin/docs/waivers.md:9-11, 30-40, 98-99`
- evidence: "Per-rule literals (what we're replacing):** every new waivable thing needs the canary to"
- pattern: 1d migration-relative phrasing ("what we're replacing", "the original … marker"); #342 internal drift
- why: § "Why one keyword" is a design argument against the retired per-rule-literal scheme, and a model writing or checking a waiver never needs it. It also contradicts itself: line 39 says making a rule waivable is "a registry entry + a doc line", while line 98 says the table *is* the registry and a row "is the only change needed". Neither is exact, because a check must also honor the new ref.
- confidence: medium
- action: rewrite
- replacement:
  - Lines 9-11: "There is **one keyword** and an **open, documented vocabulary** of rule ids. The recognizer matches `prawduct:allow` generically and reads the rule id as data, so making a rule waivable never changes the pragma syntax."
  - Lines 30-40: (delete the section)
  - Lines 98-99: "This table is the registry. A check that starts honoring a new `prawduct/<id>` adds its row here in the same change; the pragma syntax never changes."
- model_dependent: no
- machine_read: yes. `test_registry_completeness.py` parses the vocabulary heading and its table rows. The edits leave both unchanged, and lines 98-99 sit below the table.

### E-15: Region form named as a "documented future extension"
- location: `plugin/docs/waivers.md:73-74`
- evidence: "A region form (`prawduct:allow-begin` / `prawduct:allow-end`) is a documented future extension;"
- pattern: 1d time-relative phrasing; 1c (naming a non-feature anchors the model toward it)
- why: Spelling out `prawduct:allow-begin` in the spec invites a model to write it. The recognizer does not parse it, so those lines are silently left unwaived.
- confidence: medium
- action: rewrite
- replacement: "There is no region form: each waived line carries its own pragma, or the line above it does."
- model_dependent: no
- machine_read: no

### E-16: Prawduct-internal norms and test names addressed to a consumer
- location: `plugin/docs/test-report-contract.md:7-10, 106-107, 111-113`
- evidence: "runner config, because prawduct's own ratified norms say it guides and never implements"
- pattern: 1c padding; runbook guide's own rule "never explain your document's relationship to another document"
- why: The reader is a producer author in another ecosystem. `tests/test_test_report_contract.py` says so: "That reader has the doc and nothing else". The line itself admits "the norm itself lives in prawduct's repo, not in yours". "Pinned by `TestTheUndeclaredRunPath`" names a test that reader cannot see. "prawduct's own norms put goals and verification in the binding half" justifies the doc to a maintainer.
- confidence: medium
- action: rewrite
- replacement:
  - Lines 7-10: "Two properties make it honest, and a product's test setup is where they are implemented. They are a **requirement**: prawduct states them and reads their output, and installs nothing and edits no runner config."
  - Line 107: delete "Pinned by `TestTheUndeclaredRunPath`."
  - Lines 111-113: "**Advice, not contract.** What binds is the two properties above and the record this reads; *how* you produce it is yours. Every ecosystem has the two surfaces this needs: …"
- model_dependent: no
- machine_read: no

### E-17: "Never raise from the producer" stated three times, twice as reviewer-talk comments in code consumers copy
- location: `plugin/docs/test-report-contract.md:151-157, 165-168` (home: `:247-250`)
- evidence: "read-only directory or a full disk must not take the suite down with"
- pattern: 1c repetition as reinforcement; Opus 5 "Communicating" guidance: comments that justify the change talk to the reviewer, not the next reader
- why: Consumers paste this `conftest.py` into their repos. The comment "Guarded HERE, not at the call sites: one guard then covers every hook…" defends the example's design to a reviewer, and restates § "What a producer owes", which is the home of this rule.
- confidence: medium
- action: rewrite
- replacement:
  - Lines 151-157: `        # Never raise out of a hook; say so on stderr (see "What a producer owes").`
  - Lines 165-168: `    # Written FIRST, so a run that is killed or crashes leaves a record saying so` / `    # rather than the previous run's verdict sitting beside a truncated report.`
- model_dependent: no
- machine_read: yes. Tests AST-parse every Python block and assert that `except OSError` and `file=sys.stderr` are in `_write` and that neither hook contains `try:`. The edit changes comments only.

### E-18: Ticket IDs and migration-relative clauses in the telemetry contract
- location: `plugin/docs/governance-telemetry.md:45-47, 152-153, 169, 196-197, 238-240, 258`
- evidence: "The machine shape is the seam cross-project aggregation (TEL-7A4X) builds on."
- pattern: Group 2 history narrative (ticket IDs); 1d migration-relative phrasing
- why: The janitor reads this doc to interpret `review-stats`. Ticket IDs and "no longer" or "always meant" clauses describe the file's history, not the contract. The "Schema N added the key" notes **stay**: in a machine-format contract they are compatibility information for a `--json` consumer reading older reports.
- confidence: medium
- action: rewrite
- replacement: Delete the history clause and keep the contract. Worked examples:
  - Lines 45-47: delete "`build.chunk` / `plan.authored` / `discovery.session` are accommodated by the envelope and deliberately not yet produced."
  - Line 169: "The machine shape is the seam cross-project aggregation builds on."
  - Lines 196-197: "…They are **not** in `events_total`, which counts reviews." (drop "and they are no longer skips")
  - Lines 152-153: "A `learning.` kind this report has no column for counts under `unknown_kinds`."
  - Lines 238-240: "The predicates live in `lib/timewindow.py` and are shared with `tools/pr-review-yield.py`, so the two instruments grade a before/after split identically."
  - Line 258: drop "(TEL-4M9X)".
- model_dependent: no
- machine_read: no. The `--json` key block and the pinned phrase "reads here as never fired" are untouched.

### E-19: Discipline table's intro and footer carry audit citations and row history
- location: `plugin/docs/discipline.md:3-12, 24, 30-31`
- evidence: "None ships as an always-loaded corpus: each is delivered where the evidence"
- pattern: Group 2 history narrative (the "audit 2026-09-01 §3.5", "#343" and "#833" references, and "added by this table's first entry (learnings v2, 2026-09)"); 1a caps ("BOUNDARY"); #342 (lines 10-12 restate `reflection.md:48`)
- why: A product-repo reader arrives here from `reflection.md` Step 4 to check whether a lesson is already inherited. The audit and issue citations and the row-addition history do not help with that check. The closing clause of the intro restates the reflection sentence that sent them here.
- confidence: medium
- action: rewrite
- replacement:
  - Lines 3-12: "Ten lessons that governed products learned independently, two to five repos each. None ships as an always-loaded corpus: each is delivered where rules fire — in code at the moment of the action, in a Critic goal the review reads, in a methodology sentence at the step that needs it, or in a skill step when that step runs — and this table records which. A rule enters only if it is stack-agnostic, not about prawduct internals, and about building software with an agent rather than about one codebase."
  - Row 6, Rule cell: "There is no pre-existing exception; the fix-it half is bounded to BLOCKING findings"
  - Lines 30-31: delete the first sentence ("Rows 7 and 9 and the second clause of row 1 were added…"), and keep the sentence about the two carriers agreeing.
- model_dependent: no
- machine_read: yes. `tests/test_discipline_table.py` requires 6 cells per row, a numeric first cell, the Channel regex `critic goal [123]`, and the anchors. Only the Rule cell of row 6 changes.
- dup_of: `plugin/methodology/reflection.md:48` ("a product that rewrites one has paid for a rule it already inherited")

## Outside my slice

- `plugin/skills/runbook/SKILL.md:34` and `plugin/templates/runbook.md:33` repeat the overstated "best-evidenced finding" claim (E-1). The home is `runbook-authoring.md` § Read this first; correct the copies or replace them with pointers.
- `plugin/skills/runbook/SKILL.md:51-60` ("Budgets", subtraction pass, two audiences) and the header comment in `plugin/templates/runbook.md` restate `runbook-authoring.md:60-97`. The home is the guide; the skill already mandates reading it first.
- `plugin/skills/runbook/SKILL.md:154` "Non-negotiables while drafting" lists 7 items, which conflicts with the guide's four "actually non-negotiable" items (`runbook-authoring.md:99-108`). Rename it "Drafting defaults", or point to the guide.
- `plugin/skills/runbook/SKILL.md:115-130` (Step 2 derivation-source list) copies `runbook-authoring.md:1278-1292` almost word for word. The home is the guide.
- `plugin/skills/critic/review-cycle.md:545-560` restates the ledger envelope, single-writer rule and skip-unknown contract from `governance-telemetry.md:9-50`, with a different example `model` value. The home is `governance-telemetry.md`; review-cycle keeps a two-line pointer.
- `plugin/skills/critic/review-protocol.md:43` and `plugin/skills/critic/goals-1-3.md:41-42` say BLOCKING "where ratified norms exist". Align them with `norms.md` § Severity ("adopted"); see E-4.
- `plugin/methodology/planning.md:147-155` restates the `governed_by:` disposition list and `[DECISION: …]` form from `norms.md:55-58, 196-201`. They currently agree. Per the brief the home is `norms.md`, and planning.md could point to it.
