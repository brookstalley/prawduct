export const meta = {
  name: 'runbook-claim-verify',
  description: 'Adversarially verify mined runbook claims + close two research gaps',
  phases: [
    { title: 'Verify', detail: '3-vote adversarial verification per mined claim' },
    { title: 'Gaps', detail: 'targeted search on irreversible ops + machine-vs-human audience' },
  ],
}

const VOTES = 3
const KILL = 2

const VERDICT_SCHEMA = {
  type: "object", required: ["refuted", "evidence", "confidence"],
  properties: {
    refuted: { type: "boolean" },
    evidence: { type: "string" },
    confidence: { enum: ["high", "medium", "low"] },
    correctedClaim: { type: "string" },
  },
}

const GAP_SCHEMA = {
  type: "object", required: ["findings"],
  properties: {
    findings: { type: "array", maxItems: 6, items: {
      type: "object", required: ["claim", "source", "quote", "confidence"],
      properties: {
        claim: { type: "string" },
        source: { type: "string" },
        quote: { type: "string" },
        confidence: { enum: ["high", "medium", "low"] },
      },
    }},
    nothingFound: { type: "string" },
  },
}

const CLAIMS = [
  { id: "nureg-imperative", src: "NUREG-0899 (NRC, Aug 1982), https://www.nrc.gov/docs/ml1025/ml102560007.pdf",
    claim: "NUREG-0899 mandates imperative-mode phrasing and short sentence structure for emergency procedure steps, requires concrete/specific words, and prohibits imprecise adverbs such as 'frequently' and 'slowly'.",
    quote: "Sentences, clauses, and phrases should be short and written using a word order common to standard American English usage. Sentences which require the operator to do something or observe something should be written as a directive (imperative mode). ... Avoid using adverbs that are difficult to define in a precise manner (e.g., frequently, slowly)." },
  { id: "nureg-atomicity", src: "NUREG-0899 (NRC, 1982)",
    claim: "NUREG-0899 prohibits chaining a second action onto a step via a trailing THEN, giving three named failure modes: embedded actions get overlooked, they break per-step check-off/sign-off verification, and they get confused with conditional logic.",
    quote: "The logic word THEN should not be used at the end of an action to instruct the operator to perform another action within the same step, because it runs actions together. ... Actions which are embedded in this way (1) may be overlooked and not be performed, (2) make it difficult to verify the performance of each action step when a check-off or sign-off is used, and, (3) can be confused with a logic statement." },
  { id: "nureg-branching", src: "NUREG-0899 (NRC, 1982)",
    claim: "NUREG-0899 requires condition-first IF/IF NOT/WHEN...THEN branch structure, caps conditions joined by AND at four before requiring a list format, and forbids mixing AND with OR in the same step because the logic becomes ambiguous.",
    quote: "the step should begin with the words IF, IF NOT, or WHEN followed by a description of the condition or conditions (the antecedent), and the word THEN, followed by the action to be taken (the consequent). ... the word AND should not be used to join more than four conditions. If more than four conditions need to be joined, a list format should be used. ... The use of AND and OR, along with IF and THEN, within the same step should be avoided." },
  { id: "nureg-warnings", src: "NUREG-0899 (NRC, 1982)",
    claim: "NUREG-0899 requires that a WARNING/CAUTION immediately precede the step it governs, be readable without an intervening step or page turn, contain only hazard-relevant information, and contain NO operator actions; and that each action step be wholly contained on a single page.",
    quote: "WARNINGS and CAUTIONS should immediately precede the step(s) to which they refer, ... should be written so that they can be read completely without interruption by intervening steps or page turning. ... They should not contain operator actions. ... each action step should be wholly contained on a single page." },
  { id: "nureg-validation", src: "NUREG-0899 (NRC, 1982)",
    claim: "NUREG-0899 asserts desk review alone is insufficient to validate a procedure: correspondence between the procedure and real hardware/labels/units can only be adequately established by physical walk-through, and assurance that the procedure actually works requires simulation.",
    quote: "It should be noted that item 'd' above can only be adequately addressed using control room/plant walk-throughs, while item 'f' should be addressed using an approach that includes simulation." },
  { id: "qrh-branch-typography", src: "SKYbrary, 'Quick Reference Handbook (QRH)', https://skybrary.aero/articles/quick-reference-handbook-qrh",
    claim: "Aviation QRH design specifies three concrete typographic mechanisms for representing decision branches in a text procedure: an explicit condition marker symbol, lateral indentation grouping all steps belonging to one condition, and whitespace separating phases/conditional groups. QRH doctrine frames layout ergonomics as the primary defence against two named error modes: omission of an action, and performance of an undue/irrelevant/inadvertent action.",
    quote: "More than in any other document, clear and unambiguous layout ergonomics is paramount in the QRH in order to avoid any : Omission of an action (or action group), Performance of an undue/irrelevant/inadvertent action. ... The correct identification of preconditions / conditional action steps, using symbols ... The proper indenting (lateral shift) of actions belonging to the same conditional actions group, Adequate spacing between the various phases of the procedure" },
  { id: "qrh-branch-agreement", src: "SKYbrary QRH article",
    claim: "Aviation QRH doctrine requires explicit two-person agreement that a branch condition is true before any conditional step is executed, and separately requires verification of each action's result before proceeding to the next step, to allow early detection of an action slip or omission.",
    quote: "The agreement of both pilots on the 'If ....' conditions is required before performing any conditional action step ... The error-resistant QRH design should be backed-up/reinforced by adherence to operating golden rules such as the verification of each action result before proceeding to the next action step." },
  { id: "google-imperative", src: "Google developer documentation style guide, https://developers.google.com/style/procedures",
    claim: "Google's developer documentation style guide requires the first sentence of every procedural step to include an imperative verb, requires stating the location of the action before the action itself, requires one action per step, and requires that a step's result be stated after the action within the same step rather than as a separate step.",
    quote: "Make sure that the first sentence in a procedural step includes an imperative verb. ... State the location of the action before stating the action. ... use one step for each action ... State the action first and the result second." },
  { id: "aws-metadata", src: "AWS Well-Architected Framework, OPS07 'Use runbooks to perform procedures', https://docs.aws.amazon.com/wellarchitected/latest/framework/ops_ready_to_support_use_runbooks.html",
    claim: "AWS Well-Architected prescribes a minimum metadata field set for every runbook — Runbook ID, description/desired outcome, tools used, special permissions, author, last-updated date, and escalation point of contact — supplied as a copyable template; names runbook drift out of sync with system changes as an explicit anti-pattern; and prescribes progressive automation starting with short, frequently-used runbooks.",
    quote: "| Runbook ID | Description | Tools Used | Special Permissions | Runbook Author | Last Updated | Escalation POC | ... Letting runbooks drift out of sync with system changes and automation. ... As your organization matures, begin automating runbooks. Start with runbooks that are short and frequently used." },
  { id: "aws-peer-exec", src: "AWS Well-Architected OPS07 + REL12-BP05 game days",
    claim: "AWS prescribes peer execution as the validation mechanism for a new runbook — someone other than the author must run it end to end — and lists 'You document your procedures, but you never exercise them' as the first common anti-pattern for its game-day best practice.",
    quote: "Once your runbook is documented, validate it by having someone else on your team run it. ... Common anti-patterns: You document your procedures, but your never exercise them." },
  { id: "cao-rationale", src: "Cao, Chan & Elkamel, Safety 2019, 5(2):19, doi:10.3390/safety5020019",
    claim: "In a 60-participant controlled experiment, adding a one-line purpose/rationale statement to each critical step of a standard operating procedure raised adherence from a mean of 44% to 68% (F(1,53)=6.571, p=0.013, eta-squared=0.099), with no significant task-time penalty, and shifted the dominant deviation reason from intentional 'my own method is better' (43% to 10%) to unintentional slips.",
    quote: "participants assigned to use the explanatory manual had significantly higher APOP (M = 68%, SD = 39%) compared to those assigned the procedural manual (M = 44%, SD = 44%). ... Regarding task completion time, the effects were not significant for manual type (F(1, 53) = 0.331, p = 0.567)" },
  { id: "urbach-null", src: "Urbach et al., NEJM 2014;370:1029-1038, doi:10.1056/NEJMsa1308261",
    claim: "In 101 Ontario hospitals (109,341 procedures before vs 106,370 after), adopting a surgical safety checklist produced no significant reduction in operative mortality (0.71% vs 0.65%, OR 0.91, 95% CI 0.80-1.03, P=0.13) or complications (3.86% vs 3.82%, OR 0.97, P=0.29). The exposure measured was the hospital-reported date a checklist came into force, not observed compliance or quality of use.",
    quote: "The adjusted risk of death during a hospital stay or within 30 days after surgery was 0.71% ... before implementation of a surgical checklist and 0.65% ... afterward (odds ratio, 0.91; 95% CI, 0.80 to 1.03; P=0.13)." },
  { id: "ms-defect-taxonomy", src: "arXiv 2510.10074 (StepFly), Proc. ACM Softw. Eng. FSE 2026",
    claim: "An empirical dual-annotated study (Cohen's kappa = 0.78) of 92 real-world troubleshooting guides from 9 Microsoft teams found quality defects distributed as: Clarity and Precision 37.4% (dominated by 'Missing Description of the Action' and 'Unquantifiable Condition'), Database Instruction 27.2%, Data Flow 20.4%, Presentation/Structure 9.9%, Control Flow 5.1% — i.e. the most common defect in real runbooks is an under-specified action and an unmeasurable condition, not a wrong step.",
    quote: "Clarity and Precision (CP) issues are the most common in our study, accounting for 37.4% of all issues; the dominant sub-issues are 'Missing Description of the Action' and 'Unquantifiable Condition' ... Database Instruction (DI) issues rank second at 27.2% ... Data Flow (DF) and Control Flow (CF) issues account for 20.4% and 5.1%" },
  { id: "ms-dual-compat", src: "arXiv 2510.10074 (StepFly), FSE 2026",
    claim: "Microsoft researchers explicitly rejected converting runbooks into a machine-only domain-specific language, imposing a dual-compatibility requirement that procedures remain human-readable even when agents execute them, because DSL-only procedures create barriers for human practitioners and complicate long-term maintenance. They also found most of the 92 studied guides are not readily suitable for automation without substantial refinement.",
    quote: "A critical requirement in our revision process was maintaining human readability alongside LLM compatibility. We explicitly required that TSGs remain accessible and comprehensible to human SREs, not exclusively optimized for automated agents. ... Finding 4: Most TSGs, in their current form, are not readily suitable for automation due to various quality issues." },
  { id: "ms-onthefly", src: "arXiv 2510.10074 (StepFly), FSE 2026",
    claim: "When an LLM agent generates operational commands on the fly rather than executing a pre-stored exact template, three failure modes dominate: instruction drift (ignoring the provided template and rewriting the command), structural omissions (dropping sub-queries or conditions), and syntax errors (notably escape-character/regex mishandling). The mitigation is to pre-extract exact query templates offline so the model only fills parameters.",
    quote: "Our experiments identify this 'on-the-fly' generation as a primary source of error, characterized by: (1) instruction drift, where the LLM ignores templates to rewrite queries; (2) structural omissions, such as missing sub-queries or conditions; and (3) syntax errors, particularly incorrect regex formatting due to escape character mishandling." },
  { id: "nissist-ttm", src: "arXiv 2402.17531 (Nissist), Microsoft",
    claim: "In an analysis of roughly 1000 high-severity Microsoft cloud incidents over twelve months, incidents that had an associated troubleshooting guide had a 60% shorter average time-to-mitigate than incidents without one. This is observational and correlational, not experimental, and plausibly confounded because incidents with a pre-written guide may be the better-understood, more routine ones.",
    quote: "We found that incidents paired with TSGs exhibit a 60% shorter average time-to-mitigate (TTM) compared to those without TSGs, emphasizing the pivotal role played by TSGs." },
  { id: "pkg-hallucination", src: "arXiv 2605.17062 (package hallucination replication, 2026)",
    claim: "Across 199,845 paired Python and JavaScript prompts validated against PyPI and npm master lists, 2026-cohort code-generating LLMs still emit install/import references to non-existent packages at rates between 4.62% and 6.10% per model; and 127 package names were invented identically by all five evaluated models, which falsifies cross-model consensus as a detector of fabricated dependencies.",
    quote: "we measure overall hallucination rates between 4.62% (Claude Haiku 4.5) and 6.10% (GPT-5.4-mini) ... we identify a set of 127 package names (109 on PyPI, 18 on npm) that all five evaluated models invent identically" },
  { id: "itbench-ceiling", src: "ITBench-AA (IBM Research + Artificial Analysis), https://huggingface.co/blog/ibm-research/itbench-aa",
    claim: "On the ITBench-AA SRE incident-diagnosis benchmark, no frontier model reaches 50% accuracy, and longer agent trajectories correlate with worse rather than better accuracy because over-investigating agents surface co-occurring symptoms or fault-injection machinery as false positives. The benchmark measures diagnosis only — no remediation or execution — so it provides no evidence that agents can safely execute procedure steps.",
    quote: "All frontier models score below 50%, making ITBench-AA SRE one of the least saturated agentic benchmarks ... models that over-investigate tend to surface upstream fault-injection mechanisms or co-occurring symptoms as false positives ... longer trajectories do not translate to higher accuracy" },
  { id: "burian-noguidance", src: "Burian, Barshi & Dismukes, 'The Design of Emergency and Abnormal Checklists', NASA Ames, 2006",
    claim: "NASA Ames researchers stated that relatively little design guidance is available from the human-factors community for emergency and abnormal checklists, so developers generally rely on system requirements, historical precedent, and their own best judgment — and that human performance limitations under stress are a design input checklist developers often fail to appreciate.",
    quote: "Relatively little guidance is available from the human factors community and developers generally use aircraft system requirements, historical precedent, and their own best judgment to guide their design decisions." },
]

phase("Verify")
log("Adversarially verifying " + CLAIMS.length + " mined claims (" + VOTES + " votes each, " + KILL + " refutes kill)")

const verified = await pipeline(
  CLAIMS,
  (c) => parallel(
    Array.from({ length: VOTES }, (_, v) => () => agent(
      "## Adversarial Claim Verifier (voter " + (v + 1) + "/" + VOTES + ")\n\n" +
      "Be SKEPTICAL. Your job is to REFUTE this claim. " + KILL + "/" + VOTES + " refutations kill it.\n" +
      "This claim is destined for a durable engineering-standards document, so a plausible-but-wrong claim is expensive.\n\n" +
      "## Claim\n" + c.claim + "\n\n" +
      "**Attributed source:** " + c.src + "\n" +
      "**Supporting quote allegedly from that source:**\n\"" + c.quote + "\"\n\n" +
      "## Your checks\n" +
      "1. GO READ THE PRIMARY SOURCE. Use WebFetch on the source URL (or WebSearch to locate it, incl. PDF mirrors). Does the quote appear, verbatim or near-verbatim?\n" +
      "2. Is the CLAIM actually supported by the quote, or does it overreach/generalize/harden a hedge ('should'->'must', 'can improve'->'improves', correlation->causation)?\n" +
      "3. Are the numbers exactly right? Check every figure, statistic, CI, and p-value against the source.\n" +
      "4. Is the attribution correct (right authors, right document, right year, right section)?\n" +
      "5. WebSearch for contradicting or superseding evidence.\n" +
      "6. Is the source authoritative enough for the claim's strength, and is it current?\n\n" +
      "**refuted=true** if: quote not found / claim overreaches the quote / any figure wrong / misattributed / contradicted / source too weak.\n" +
      "**refuted=false** ONLY if you verified the quote in the primary source AND the claim is a faithful, non-hardened reading of it.\n" +
      "Default to refuted=true if you could not access the source.\n" +
      "If the claim is *nearly* right but needs correction, set refuted as you judge AND fill correctedClaim with the accurate version.\n\n" +
      "Structured output only. Evidence MUST cite what you actually read.",
      { label: "v" + v + ":" + c.id, phase: "Verify", schema: VERDICT_SCHEMA }
    ))
  ).then(vs => {
    const valid = vs.filter(Boolean)
    const refs = valid.filter(v => v.refuted).length
    const survives = valid.length >= KILL && refs < KILL
    log(c.id + ": " + (valid.length - refs) + "-" + refs + " " + (survives ? "OK" : refs >= KILL ? "KILLED" : "?"))
    return { ...c, votes: valid, refutes: refs, survives, isKilled: refs >= KILL,
             corrections: valid.map(v => v.correctedClaim).filter(Boolean) }
  })
)

const ok = verified.filter(Boolean).filter(c => c.survives)
const dead = verified.filter(Boolean).filter(c => c.isKilled)
log("Verify done: " + ok.length + " confirmed, " + dead.length + " killed")

phase("Gaps")
const GAPS = [
  { id: "irreversible-ops",
    q: "Find authoritative guidance on writing procedures for IRREVERSIBLE, one-shot, or un-undoable operations — where the operator cannot roll back. Search: field service manual conventions for destructive steps; embedded device firmware flashing / bricking risk procedures; 'point of no return' procedure design; NASA/aviation 'no-go' and abort-criteria doctrine; surgical 'time out' before irreversible incision; ANSI Z535.6 safety information in product manuals (DANGER/WARNING/CAUTION/NOTICE hierarchy and placement rules); IEC 82079-1 (preparation of instructions for use) requirements on safety messages and step structure. What do these mandate about marking a destructive step, stating the abort criterion BEFORE the point of no return, and pre-flight verification of preconditions?" },
  { id: "machine-vs-human",
    q: "Find guidance or research on whether documentation optimized for MACHINE/LLM-agent consumption conflicts with documentation optimized for stressed human readers. Search 2024-2026: agent-readable runbooks, 'docs for agents', structured procedure formats for LLM execution, llms.txt, machine-readable SOP schemas, and any study comparing the two audiences. Also: guidance on human-in-the-loop checkpoints and safety constraints when an AI agent executes operational procedures autonomously. Report only what you can source." },
  { id: "regulated-audited",
    q: "Find authoritative requirements for operational procedures in REGULATED environments where the procedure is an audited artifact: FDA 21 CFR Part 11 and GxP standard operating procedure requirements, ISO 13485 / IEC 62304 for medical device software, ITIL 4 and ISO/IEC 20000 on documented procedures, and change-control requirements. Specifically: what do these mandate about procedure version control, approval, training records, and evidence that a procedure was FOLLOWED (execution records/signoffs) as distinct from the procedure existing?" },
  { id: "runbook-anatomy-evidence",
    q: "Find any EVIDENCE-BASED (not merely conventional) source on what fields or sections an operational runbook should contain — trigger/entry conditions, prerequisites, abort criteria, expected duration, blast radius, ownership, last-verified date. Search: IEEE 1023 (nuclear procedure guidance), INPO procedure standards, IEC 82079-1 content requirements, military technical manual specifications (MIL-STD-38784, MIL-STD-40051), and any empirical study measuring which procedure elements affect performance. Distinguish mandated standards from practitioner convention." },
]

const gapResults = await parallel(GAPS.map(g => () => agent(
  "## Targeted research: " + g.id + "\n\n" + g.q + "\n\n" +
  "## Rules\n" +
  "- Use WebSearch then WebFetch. Prefer standards bodies, regulators, and peer-reviewed work over vendor blogs.\n" +
  "- Report ONLY claims you verified against a source you actually fetched. Include a verbatim quote for each.\n" +
  "- If you cannot source something, say so in nothingFound rather than inventing it. An honest gap is more useful than a plausible guess.\n" +
  "- Mark confidence: high = primary standard/peer-reviewed, quote verified; medium = secondary but reputable; low = single weak source.\n\n" +
  "Structured output only.",
  { label: "gap:" + g.id, phase: "Gaps", schema: GAP_SCHEMA }
)))

return {
  confirmed: ok.map(c => ({ id: c.id, claim: c.claim, src: c.src, vote: (c.votes.length - c.refutes) + "-" + c.refutes,
    corrections: c.corrections, evidence: c.votes.filter(v => !v.refuted).map(v => v.evidence) })),
  killed: dead.map(c => ({ id: c.id, claim: c.claim, vote: (c.votes.length - c.refutes) + "-" + c.refutes,
    why: c.votes.filter(v => v.refuted).map(v => v.evidence), corrections: c.corrections })),
  gaps: GAPS.map((g, i) => ({ id: g.id, result: gapResults[i] })),
  stats: { claims: CLAIMS.length, confirmed: ok.length, killed: dead.length },
}