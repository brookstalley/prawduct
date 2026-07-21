# Runbook Authoring Research — Checkpoint

**Purpose:** produce a durable best-practices artifact in `docs/` that an LLM in a prawduct
context consumes to generate world-class runbooks for any project (any language, frontend /
backend / embedded / data / mobile), where the *generated runbook* must be immediately useful
to humans.

**Scope (owner-confirmed 2026-07-20):** "runbook" = any pre-written procedure for an anticipated
operational task — incident response, deploy/rollback, release, provisioning, disaster recovery,
routine maintenance, on-call diagnostics. EXCLUDES onboarding docs, architecture docs, tutorials,
local dev setup. Deliverable this pass = **the `docs/` guide only** (no template, no skill —
those are a proposed follow-on).

**Status: COMPLETE.** All four research passes landed or were salvaged. Artifact written and
committed at `docs/runbook-authoring.md`.

- Pass 3 (verification): 57/61 agents; 8 claims confirmed, 11 killed. Verdicts in
  `raw/pass3-verdicts-final.txt` (gitignored; local only). Two kills were live defects in the committed guide (the
  package-hallucination consensus claim and the rationale-experiment scope) — both corrected.
- Pass 4: died before returning, but **all 8 investigations were recovered from its journal** —
  see `raw/pass4-salvage-8-investigations.txt` (gitignored; local only). Its adversarial *challenge* phase did not run, so those
  findings are marked ○ in the artifact.
- Still open: the 4 gap searches (irreversible ops, regulated, machine-vs-human, anatomy evidence)
  died on the session limit. Scripts are saved and resumable if ever wanted.

---

## Provenance / how to resume

| Pass | Run ID | What it covered | State |
|---|---|---|---|
| 1 | `wf_b80d5c39-62b` | doctrine, structure, style, maintenance, LLM | DONE → `raw/pass1-*.json` |
| 2 | `wf_c2c2c2bf-ebe` | human factors, domain variation, LLM | DONE → `raw/pass2-*.json` |
| 3 | `wf_5f51f52d-5a5` | adversarial verification of 19 mined claims + 4 gap searches | in flight at checkpoint |
| 4 | `wf_f035fe86-4d6` | postmortems, embedded/field, QRH selection rules, checklist implementation evidence, domain variation, cognitive load design, alert linkage, agent execution safety | in flight at checkpoint |

Scripts for 3 & 4 are saved in `raw/`. Resume either with
`Workflow({scriptPath: "<raw/…js>", resumeFromRunId: "<run id>"})` — unchanged agent calls
replay from cache. Journals for 1 & 2 in `raw/journal-pass*/journal.jsonl` (one `result` line
per agent, with full return values).

Cost so far: ~215 agents, ~7M subagent tokens across passes 1–2.

---

## Method note (why this research was worth doing)

Pass 1 adversarially verified 25 extracted claims with 3 independent refutation votes each and
**killed 9 of them (36%)** — including several that are widely repeated and that a model would
confidently generate from memory. That kill rate is the justification for the whole exercise:
this domain is full of plausible-sounding, unevidenced claims.

---

## CONFIRMED FINDINGS (survived 3-vote adversarial verification)

### A. The strong evidence is from aviation / safety science, not software

**A1. Verification steps must report an observed value, never an acknowledgment token.**
Degani & Wiener, NASA CR-177549 (1991) §6.2.3 "Checklist Ambiguity", and the peer-reviewed
version, *Human Factors* 35(2):28–43 (1993), guideline #1: "the response should always portray
the actual status or the value of the item." Grounded in ASRS report #76798: "'checked' and
'set' can be said too easily without any sound verification"; prescribed form is
`Altimeters—30.10`, not `checked`. Reaffirmed 26 years later by FAA AC 120-71B §5.4: "The
generic responses of 'set' or 'checked' may not be very informative."
→ **Rule:** a step says *record the replica count returned by `<cmd>`*, not *confirm replicas
are healthy*. Confidence: HIGH. Caveat: source modality is "should/whenever possible"; transfer
to IT runbooks is our inference, though the mechanism (verbal response decoupled from perceptual
verification) is generic.

**A2. Order by criticality, not by system topology — most critical items FIRST.**
Degani & Wiener, NASA report Appendix A guideline (10) / journal guideline 6: "The most critical
items … should be listed as close as possible to the beginning." Rationale §7.2.4: "the
probability of accomplishing the subsequent items slowly diminishes as time progresses, since
there is more chance for interruptions and distractions to occur." **This guideline explicitly
overrides** sequencing by workspace/system flow (8/4) and by external dependencies (9/5) — "In
most cases where this occurs, this guideline (10) should take precedence." Grounded in the Delta
1141 accident (TAXI checklist with "Flaps" at the end). Confidence: HIGH.
Caveats to preserve: "in most cases" hedge; guidelines "are not specifications"; "monotonically"
is our formalization of "slowly diminishes"; the source defines critical as *accident-causing on
omission*, NOT as irreversible — do not silently add "irreversible"; the authors' full position
is first-AND-again for transient killer items.

**A3. Execution method is a structural safety property, not formatting.**
NASA CR-177549 §3.1.4. *Challenge-verification-response* uses the list as a backup to verify an
already-completed configuration → preserves "configuration redundancy". *Do-list*
(call-do-response) leads the operator step-by-step → destroys that redundancy, so "a mistake can
easily pass unnoticed once the sequence is interrupted." Confidence: MEDIUM (2-1).
IMPORTANT WORDING CORRECTIONS: the strings "read-do" and "do-confirm" appear **zero** times in
Degani & Wiener — those are Gawande's terms (from Daniel Boorman at Boeing); the mapping is ours.
The source also hedges: "there is no absolute boundary for each method, and variations as well as
combinations of these methods exist."
→ **Rule:** a step-by-step script executed cold is the WEAKER form. Where the operator can do the
work independently, a verification-oriented checklist retains redundancy the script destroys.

**A4. Length is a first-order defect.**
Degani & Wiener 1993, citing Swain & Guttman (1983) THERP/NUREG/CR-1278: "as the list of items
grows, there may be a higher probability of overlooking any given item"; and "it carries the risk
that some pilots might choose not to use the checklist or may conduct the procedure poorly
because of its length." Their own field data: with lengthy checklists crews degraded into reading
it as a do-list, "sacrific[ing] the setup redundancy embedded in the checklist." Remedy =
decomposition into task-scoped chunks, grouped by system/function and **physically separated in
the layout** (via Wickens 1987). WHO Surgical Safety Checklist corroborates the shape: 19 items
across **three** pause points where "the entire team stop all other activity for a few moments."
Confidence: HIGH for length/decomposition; MEDIUM (2-1) for the WHO pause-point framing.
Caveats: no experiment manipulated length — support is an HRA-handbook hedge ("may be"), pilot
self-report, and field observation, so do NOT say "causally linked". Neither WHO nor Ariadne Labs
states *why* those three moments were chosen — the error-recovery-cost reading is OUR inference.
Degani's own counterweights: shortening means some misconfigurations go unchecked; and "the lack
of indication that a task-checklist is fully completed is one of the handicaps" of decomposition.

**A5. Deviation from a procedure is first a DOCUMENT-DEFECT signal.**
Hale & Borys, "Working to rule, or working safely? Part 1", *Safety Science* 55:207–221 (2013),
Table 1, column "Rule-related factors" — seven properties, **all** positively correlated with
tendency to violate: difficult to understand; difficult to comply/work with; violation needed to
get the job done; outdated rule; conflicting rules with no priorities given; rule seen as
inappropriate because the rule-maker has no knowledge of the reality of the activity; too many
rules. (Verifier rendered the PDF at 200dpi to confirm all seven carry the *filled* bullet —
correlated — uniquely among the four columns.) Confidence: HIGH.
Caveats: correlational; narrative synthesis over heterogeneous self-report occupational-safety
studies; industrial domain, so software transfer is analogical. **The two quantitative sub-studies
inside this review (Elling's Dutch railway percentages; Embrey's 400-respondent chemical survey)
were BOTH REFUTED — never cite those figures.**

**A6. Drift is structural, not negligent.**
Dekker, "Failure to adapt or adaptations that fail", *Applied Ergonomics* 34:233–238 (2003):
"Rules that are overdesigned (written for tightly coupled situations, for the 'worst-case') do
not match actual work most of the time … This mismatch creates an inherently unstable situation
that generates pressure for change (Snook, 2000)", producing "practical drift" / "fine-tuning"
where "Deviance (from the original rules) becomes normalized; non-conformity becomes routine
(Vaughan, 1996)." Dekker rejects the negligence reading and says organizations should "resist
trying to close [the gap] by simply telling people to comply." Hale & Borys supply the two-model
framing (rules as static imposed limits vs. dynamic situated constructions) but **do NOT endorse
model 2** — they propose synthesis. Confidence: HIGH.
Caveats: overdesign is one of FOUR ingredients Dekker lists — don't escalate to "the" cause;
evidence is theoretical synthesis over accident case studies, not measurement; Dekker never uses
"procedure rot" — his mechanism is *practice drifting from a static rule*, the mirror image of
the software case where *the system changes under an unmaintained document*.

**A7. The double bind (pass 2).** Dekker p.235: "If rote rule following persists in the face of
cues that suggests procedures should be adapted, this may lead to unsafe outcomes… If adaptations
to unanticipated conditions are attempted without complete knowledge of circumstance or certainty
of outcome, unsafe results may occur too." p.236: "Tightening procedural adherence… does not
remove the double bind. In fact, it may tighten the double bind." Confidence: HIGH (3-0).
→ **Rule:** neither blind compliance nor free improvisation is a safe default; the procedure must
tell the reader *when it no longer applies* and what to do then.

### B. The software canon is doctrine, NOT evidence — say so explicitly

**B1. Google SRE's "~3x improvement in MTTR" from playbooks is unevidenced.** Verified verbatim
on the live page (SRE Book ch.1); a full-page fetch found **no citation, footnote, N, date range,
or definition of the measurement**. Self-undercut by Google's own later publication, Davidovic,
"Incident Metrics in SRE", which concludes MTTR-style statistics "are poorly suited for decision
making or trend analysis in the context of production incidents." The SRE Workbook separately
describes step-by-step playbooks as internally "contentious". Confidence: HIGH.

**B2. NIST SP 800-61r3's playbook-usability claim is unevidenced.** p.9: "Formatting procedures
within a playbook instead of another format *can* improve their usability." Verified by grepping
the official PDF for all 6 occurrences of "playbook": the usability sentence carries no bracket
reference, and the reference list contains no human-factors or usability source at all.
Note the modality is "CAN improve", weaker than "improves". Confidence: HIGH.

**B3. NIST's coverage rule (this one is useful).** SP 800-61r3 §2.3, pp.8–9: "While it is
impossible to have detailed procedures for every possible situation, organizations should
consider documenting procedures for responding to the most common types of incidents and threats.
Organizations should also develop and maintain procedures for particularly important processes
that may be urgently needed during emergency situations, such as redeploying the organization's
primary authentication platform." Confidence: HIGH.
→ **Rule:** coverage is driven by frequency AND by recovery-criticality; the second category is
precisely the one teams under-write *because it is by definition rare*.
Caveat: modality is "should CONSIDER" for prong 1, stronger "should develop and maintain" for
prong 2; NIST says "procedures"/"playbooks", never "runbooks".

**B4. Document + exercise, not document alone.** SRE Book ch.1: playbooks "in addition to"
Wheel of Misfortune. ch.28: after those sessions Google "adjust[s] their playbooks … to provide
additional information or context for what the ideal responses would have been" — drilling feeds
authoring, bidirectionally. PagerDuty: "An untested alert is equivalent to not having an alert at
all." Confidence: MEDIUM — purely doctrinal, no data.
Caveats: Google never says playbooks are *insufficient* — "in addition to" means both are used;
PagerDuty's line is about ALERTS and aphoristic; extending it to runbooks is our inference.

**B5. Authority is part of the procedure (major incidents).** PagerDuty: "Announce all
suggestions for resolution to the Incident Commander, it is their decision on how to proceed, do
not follow any actions unless told to do so!" The IC needs "Deep technical knowledge not
required!", "become[s] the highest ranking individual on any major incident call, regardless of
their day-to-day rank", and "is NOT a resolver". Confidence: MEDIUM (2-1).
SCOPE DEFECT to carry: applies to MAJOR incidents (SEV-2+) with an established IC; for routine
incidents no IC exists and this does not bind.
→ **Rule:** procedures should encode *who authorizes* a remediation step, not merely what it is.

### C. Cognitive state of the reader — honest numbers (pass 2)

**C1. Stress impairs working memory, but the effect is SMALL and load-conditional.**
Shields, Sazma & Yonelinas, *Neurosci. Biobehav. Rev.* 68:651–668 (2016), meta-analysis:
51 studies, 223 effect sizes, 2,486 participants. Overall WM effect g+ = **-0.197**
(95% CI [-0.330, -0.064], p=.005). Concentrated under high load (g+ = **-0.303**, p=.005) and
essentially absent under non-high load (g+ = -0.049, p=.404; between-group p=.023). Overall
effect across all executive functions g+ = -0.151. Confidence: HIGH.
IMPORTANT: the high-load moderation that most directly grounds "keep procedures short" **drops to
marginal (p=.054) once study precision is controlled.** Do not present these as large effects.
Also: stress *enhances* response inhibition (g+ = +0.296) while *impairing* cognitive/interference
inhibition (g+ = -0.208) — stress is not a single scalar degradation (MEDIUM, 2-1, fragile).

**C2. Fatigue is the strong quantitative anchor.** Dawson & Reid, *Nature* 388:235 (1997):
performance declines ~0.74%/hour between the 10th and 26th hour awake; **17 h awake ≈ 0.05% BAC,
24 h awake ≈ 0.10% BAC**. Independently replicated by Williamson & Feyer, *OEM* (2000) in a
different lab/population. Confidence: HIGH.
Caveats: the ~90% variance figure is a fit to GROUP-MEAN performance — never report it as 90% of
an individual's variance; Dawson & Reid is a one-page Letter; time-awake is confounded with
circadian phase (17 h = 03:00, 24 h = 08:00).

**C3. Surprise costs place-keeping.** NLR for EASA (2018), *Startle Effect Management*: surprise
"impairs the working memory"; cognitive responses "may involve the inability to remember the
current operating procedures"; a pilot "can … lose track of where he was in going through a
checklist." Confidence: MEDIUM. Attribute to **NLR-for-EASA**, not EASA as regulator (the report
carries an explicit agency disclaimer). The "~one third of participants" figure (Martin et al.
2016, B737 simulator) is abstract-level provenance with no retrievable N — MEDIUM at best.

**C4. Author/user perception gap.** Mendoza et al., *Int. J. Industrial Ergonomics* 100:103564
(2024): users self-report deviating M=30.8% vs administrators' estimate M=19.8%; administrators
attribute deviation to unintentional use error while "users never recognized those errors and
reported primarily intentional reasons for deviation", arising from "the disconnect between those
who write the procedures and those who complete the task." Confidence: MEDIUM.
Caveats: n=26 users at ONE chemical site + 13 administrators, one corporation; paper itself says
results "cannot be assumed to generalize"; **no inferential test** on the 30.8 vs 19.8 gap and the
SDs (33.5, 24.5) exceed the 11-point difference. Shares authors with Peres et al. 2020 — not
independent confirmations.

**C5. Compliance is often blame-protection.** Peres, Smith & Sasangohar, *J. Loss Prev. Process
Ind.* (2020): "adherence to procedures is often motivated by potential liability issues instead of
genuine concerns for safety." Confidence: MEDIUM. Qualitative interview study; "often" is an
analyst's characterization, not a rate; do NOT attach a percentage; do NOT call it "malicious
compliance" (not the paper's term, and means something else).

---

## MINED BUT **NOT YET VERIFIED** (pass 3 was adjudicating these — treat as PROVISIONAL)

Full text in `raw/pass1-mined-unverified-claims.txt`. These fell below pass 1's 25-claim verify
cap. **Do not put any of these in the artifact without a verification verdict** — pass 1's 36%
kill rate applies here too.

- **NUREG-0899 (NRC, 1982)** — the most concrete writing rules found anywhere: imperative mode,
  short clauses, concrete words, no imprecise adverbs ("frequently", "slowly"); **no trailing THEN
  chaining a second action** (3 named failure modes: overlooked, breaks per-step sign-off,
  confused with logic); condition-first `IF/IF NOT/WHEN … THEN`, **max 4 conditions joined by AND**
  before a list format is required, **never mix AND with OR** in one step; WARNING/CAUTION
  immediately precedes its step, readable without a page turn, contains **no operator actions**;
  each action step wholly on one page; validation requires physical walk-through + simulation, not
  desk review.
- **Aviation QRH (SKYbrary)** — branch representation: explicit condition-marker symbol, lateral
  indentation grouping steps under a condition, whitespace between conditional groups; layout
  ergonomics as the defence against "omission of an action" and "performance of an
  undue/irrelevant/inadvertent action"; **both pilots must agree the condition is true before any
  conditional step**; verify each action's result before proceeding.
- **Google developer style guide** — imperative verb in the first sentence of every step; state
  the location before the action; one action per step; state action first, result second.
- **AWS Well-Architected OPS07/REL12** — runbook metadata field set (ID, description/desired
  outcome, tools, special permissions, author, last-updated, escalation POC); **peer execution** as
  the validation mechanism ("validate it by having someone else on your team run it"); drift named
  as an anti-pattern; progressive automation starting with short, frequently-used runbooks;
  "You document your procedures, but you never exercise them" as the #1 game-day anti-pattern.
- **Cao, Chan & Elkamel, *Safety* 2019, 5(2):19** — 60-participant controlled experiment: adding a
  one-line rationale to each critical step raised adherence **44% → 68%** (F(1,53)=6.571, p=0.013,
  η²=0.099) with **no significant time penalty**; intentional "my own method is better" deviations
  fell 43% → 10%. Conditional on the reader being able to comprehend the explanation
  (non-engineering participants: no significant benefit).
- **Urbach et al., NEJM 2014;370:1029-1038** — 101 Ontario hospitals, 109,341 vs 106,370
  procedures: **no** significant mortality reduction (0.71% → 0.65%, OR 0.91, CI 0.80–1.03, P=0.13)
  or complications (3.86% → 3.82%, OR 0.97, P=0.29). Exposure measured = the hospital-reported
  *date a checklist came into force*, not observed compliance.
- **Microsoft StepFly (arXiv 2510.10074, FSE 2026)** — 92 real production troubleshooting guides,
  9 teams, dual-annotated κ=0.78. Defect taxonomy: **Clarity & Precision 37.4%** (dominated by
  "Missing Description of the Action" and "Unquantifiable Condition"), Database Instruction 27.2%,
  Data Flow 20.4%, Presentation/Structure 9.9%, Control Flow 5.1%. "Finding 4: Most TSGs, in their
  current form, are not readily suitable for automation." Explicit **dual-compatibility
  requirement**: "We explicitly required that TSGs remain accessible and comprehensible to human
  SREs, not exclusively optimized for automated agents." On-the-fly LLM command generation fails via
  instruction drift, structural omissions, syntax/escape errors → pre-extract exact templates.
  Structural profile: ~3K tokens, 5–15 steps, 4.4 embedded query templates.
- **Nissist (arXiv 2402.17531)** — ~1000 high-sev Microsoft incidents/12 months: incidents with a
  TSG had **60% shorter average TTM**. Observational and confounded (guided incidents may be the
  better-understood ones). Rejects fully autonomous execution on safety grounds; hands
  non-executable actions back to the on-call engineer.
- **Package hallucination replication (arXiv 2605.17062, 2026)** — 199,845 paired Python/JS prompts
  vs PyPI/npm master lists: 2026-cohort models still invent non-existent packages at
  **4.62%–6.10%**; **127 package names invented identically by all five models** → cross-model
  consensus does NOT detect fabricated dependencies; 53 remained attacker-registrable after
  coordinated disclosure.
- **ITBench-AA (IBM Research + Artificial Analysis)** — no frontier model reaches 50% on SRE
  incident diagnosis; longer agent trajectories correlate with *worse* accuracy; benchmark covers
  diagnosis only, no remediation → no evidence agents can safely *execute* procedure steps.
- **Burian et al., NASA Ames (2006)** — "Relatively little guidance is available from the human
  factors community and developers generally use aircraft system requirements, historical
  precedent, and their own best judgment"; human performance limits under stress are the exemplar
  of an under-appreciated design input.

---

## REFUTED — DO NOT REINTRODUCE

These were killed by adversarial verification. They are plausible, widely repeated, and a model
will regenerate them from memory. The artifact should carry this list so future agents don't.

From pass 1:
- Delta 1141 "sub-one-second challenge-to-response gap" as *measured* evidence of hollow
  verification (0-3).
- PagerDuty requiring every alert to link a runbook as a hard gate (1-2).
- NIST SP 800-61r3 recommending procedures be periodically tested to verify accuracy (0-3).
- Scotland's "36.6% reduction in post-surgical deaths" from the WHO checklist (1-2).
- Dekker's "procedural deviation is not a discriminator between safe and unsafe outcomes" (0-3).
- Dekker's "enforcement pressure is counterproductive / shifts the response criterion" (0-3).
- Elling's Dutch-railway percentages (3% use often, 79% too many rules, …) (0-3).
- Embrey's 400-respondent chemical-industry percentages (62% couldn't finish in time, …) (0-3).
- The Swissair 111 double-bind case as Dekker's worked example (1-2).

From pass 2 (13 killed), notably:
- Error reports understate deviation ~4× (0-3).
- Deviation concentrates on frequent rather than rare tasks (0-3).
- Deviation is majority behavior driven by time-saving under supervisor pressure (0-3).
- Experience predicts reduced procedure use (0-3).
- Startle halts action for a measurable 100 ms–10 s (0-3).
- Arousal alone narrows attention without a threatening stimulus (0-3).
- Visual short-term memory capacity K falls with arousal (0-3).

**Meta-caveat that must survive into the artifact:** modality drift was pervasive — verifiers
repeatedly caught claims hardening "should where possible" → "must", "can improve" → "improves",
"diminishes" → "monotonically", correlational → "causally linked". Preserve hedges.

**Domain-transfer caveat:** every high-confidence finding comes from aviation, surgery, or
industrial safety. None studied software runbooks. The mechanisms are generic to human procedure
execution and Degani & Wiener explicitly sanction cross-industry application, but this is
analogical extrapolation and the artifact must say so rather than implying measured IT findings.

---

## SYNTHESIS DECISIONS ALREADY MADE (carry into the artifact)

1. **Spine finding #1 — derivation over generation.** The single highest-leverage rule for an LLM
   authoring a runbook: never *generate* a command, *derive* it from the repository (CI config,
   Makefile, package scripts, deploy manifests, alert definitions). Justified by the package-
   hallucination data (4.6–6.1%, and cross-model consensus fails) plus StepFly's on-the-fly
   generation failure modes. A prawduct agent has the repo in hand, so this is enforceable in a
   way it isn't for a generic assistant. Verification must go to the authoritative system, never
   to a second model.

2. **Spine finding #2 — the dominant real-world defect is the unmeasurable condition.** Microsoft's
   92-runbook study puts "Missing Description of the Action" + "Unquantifiable Condition" at the
   top (37.4% cluster). This is *exactly* what LLMs produce by default ("verify the service is
   healthy") and it maps onto Degani & Wiener's observed-value rule (A1). These two independent
   lines converging is the artifact's strongest single rule.

3. **The rationale/length tension is real and must be resolved, not ignored.** Cao et al. says
   per-step rationale raises adherence 44% → 68% with no time cost. Degani & Wiener says length is
   a first-order defect. Resolution to argue: rationale belongs *adjacent to* the step but
   *visually separated*, so the executing eye skips it and the confused eye finds it. Worked
   example available in-repo: `docs/release-process.md` step 2 carries excellent rationale but
   embeds it in the step, making the step long.

4. **Existing prawduct integration points** (three artifacts point at runbooks; none says how to
   write one — this is the documented gap the artifact fills):
   - `templates/operational-spec.md` → "Failure Recovery" says "High-risk: runbooks, escalation
     procedures, failover, incident response"
   - `templates/observability-strategy.md` → "What You Get" scenarios are effectively runbook
     triggers ("When X happens, you can Y")
   - `templates/unattended-operation/failure-recovery-spec.md` → `## Recovery Procedures`
   - `docs/release-process.md` is itself a runbook and can serve as the dogfood example.

5. **No backlog parent exists** (grep of `.prawduct/backlog.md` for runbook-as-capability found
   only internal uses of the word). Principle 6 requires filing one — do this at close-out.

6. **Proportionality (Principle 11) must be built in.** The artifact must not push a family app
   toward nuclear-grade procedure standards. Expect a tiering rule keyed on blast radius /
   reversibility / who executes it.

---

## OUTCOME

`docs/runbook-authoring.md` — committed. Sections: what a runbook is · which to write first · how it
gets found · the reader model · proportionality tiers · 8 invariants · execution form and memory
items · anatomy · writing rules · branching and irreversible steps · domain adaptation · maintenance
and rehearsal · authoring protocol for a model · 26-point self-review · evidence appendix.

## IF RESUMING

The four dead gap searches are the only real remainder, and the artifact is honest about the gap.
Resume with:
`Workflow({name: "runbook-claim-verify", resumeFromRunId: "wf_5f51f52d-5a5"})`
(the script is committed at `.claude/workflows/runbook-claim-verify-4.js`; the `raw/` copies are
gitignored and exist only on the machine that ran the research)
— completed agents replay from cache, so only the 4 failed gap agents re-run.

A natural follow-on, deliberately out of scope this pass: `templates/runbook.md` and a
`/prawduct:runbook` skill that applies this guide to a specific repo.
