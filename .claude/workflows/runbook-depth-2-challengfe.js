export const meta = {
  name: 'runbook-depth-2',
  description: 'Close remaining runbook research gaps: real postmortems, domain variation, aviation selection rules, checklist implementation evidence',
  phases: [
    { title: 'Investigate', detail: '8 parallel targeted investigations' },
    { title: 'Challenge', detail: 'adversarially challenge each investigation\u2019s central claims' },
  ],
}

const FIND_SCHEMA = {
  type: "object", required: ["findings"],
  properties: {
    findings: { type: "array", maxItems: 8, items: {
      type: "object", required: ["claim", "source", "quote", "confidence", "transferable"],
      properties: {
        claim: { type: "string" },
        source: { type: "string", description: "Full citation + URL actually fetched" },
        quote: { type: "string", description: "Verbatim from the source" },
        confidence: { enum: ["high", "medium", "low"] },
        transferable: { type: "string", description: "The concrete, technology-agnostic authoring rule this implies, or 'none' if it does not generalize" },
      },
    }},
    nothingFound: { type: "string", description: "What you searched for and could NOT source. Be specific and honest." },
  },
}

const CHALLENGE_SCHEMA = {
  type: "object", required: ["survives", "assessment"],
  properties: {
    survives: { type: "array", items: { type: "string" }, description: "claim texts that withstood challenge" },
    killed: { type: "array", items: { type: "string" }, description: "claim texts that failed, with reason" },
    assessment: { type: "string" },
  },
}

const LINES = [
  { id: "postmortems", label: "runbook-as-contributing-factor postmortems",
    q: "Find PUBLIC, NAMED incident postmortems in which a runbook, playbook, or written operational procedure was itself identified as a contributing or causal factor — not merely absent, but present and wrong, stale, ambiguous, or followed into failure.\n\nSearch specifically: the AWS S3 us-east-1 outage Feb 2017 (playbook/command-argument issue); the GitLab.com database incident Jan 2017 (backup/restore procedures found non-functional); Cloudflare outages (July 2019, June 2022, Oct/Nov 2025) postmortems mentioning procedure or runbook; Google Cloud incident reports; Slack, Roblox 2021 (73-hour outage), Facebook/Meta Oct 2021 (out-of-band access and the documented procedure), Knight Capital 2012 (deployment procedure), Atlassian April 2022 (script/runbook misuse in the multi-week outage); Salesforce May 2021 (DNS change procedure); the 2024 CrowdStrike incident; and public 'chaos'/game-day writeups where the runbook failed in the drill.\n\nAlso search NASA/NTSB/CAIB and process-industry investigations (Texas City 2005, Deepwater Horizon, Three Mile Island EOP findings, Air France 447, Swissair 111 TSB report) where procedure quality was a formal finding.\n\nFor each: name the incident, the date, the exact procedural defect, and quote the postmortem. Prefer first-party postmortems and official investigation reports over journalism." },

  { id: "embedded-field", label: "embedded / field service / irreversible hardware ops",
    q: "Find authoritative guidance on operational procedures for EMBEDDED SYSTEMS and PHYSICALLY-SERVICED DEVICES, where the operator may have no remote shell, an operation may be irreversible (firmware flashing, fuse burning, secure-boot key provisioning, bricking), and recovery may require physical access or RMA.\n\nSearch: IPC/IEEE field service manual standards; IEC 82079-1:2019 'Preparation of information for use (instructions for use) of products' — its requirements on structure, safety messages, step design, and completeness; ANSI Z535.6 (safety information in product manuals) DANGER/WARNING/CAUTION/NOTICE hierarchy and the rule about placement relative to the hazard; automotive/aerospace maintenance manual specs (ATA iSpec 2200, S1000D) on procedural data modules, preliminary requirements (tools, spares, safety), and 'close-out' steps; military MIL-STD-40051 procedural step rules; and vendor firmware-update guidance on anti-bricking (power loss, verification before commit, A/B partitions, recovery mode).\n\nWhat do these mandate that a cloud runbook would omit? Especially: pre-condition verification before an irreversible step, tool/spare/consumable lists, and what to do when the step cannot be undone." },

  { id: "qrh-selection", label: "aviation read-do vs do-confirm selection + memory items",
    q: "Find primary aviation doctrine on WHEN a procedure should be read-do (call-do-response) versus do-confirm (challenge-response), and on 'memory items' / 'immediate action items' / 'recall items'.\n\nSearch: FAA AC 120-71B (Standard Operating Procedures and Pilot Monitoring Duties) and AC 120-64; Boeing and Airbus QRH design philosophy documents and flight-crew training manuals; the Flight Safety Foundation; NASA Ames Burian/Barshi/Dismukes 'The Design of Emergency and Abnormal Checklists' (2005-2006) and related NASA technical reports; EASA/ICAO guidance.\n\nSpecifically: why do memory items exist, how many items are they deliberately limited to and on what basis, what criteria decide that an action becomes a memory item versus a read step, and what selection rule chooses read-do vs do-confirm for a given procedure? Quote the doctrine." },

  { id: "checklist-implementation", label: "checklist content vs implementation evidence",
    q: "Resolve the discrepancy in the surgical-checklist literature and extract the transferable lesson.\n\nCompare: Haynes et al. 2009 NEJM (WHO Surgical Safety Checklist, 8 hospitals, mortality 1.5%->0.8%, complications 11%->7%) against Urbach et al. 2014 NEJM (101 Ontario hospitals, null result) and any other failed replications or meta-analyses (e.g. Cochrane reviews, Bergs et al. meta-analysis, the Norwegian stepped-wedge trial by Haugen et al.).\n\nWhat explains the difference? Search specifically for analyses attributing it to IMPLEMENTATION quality vs checklist CONTENT: compliance/completion rates, whether the checklist was performed as a team pause vs ticked as paperwork, training and leadership engagement, and the 'checklist as artifact vs checklist as practice' argument (look for Bosk et al. 'Reality check for checklists' in The Lancet, and Catchpole/Russ critiques).\n\nThe transferable question: does merely HAVING a correct written procedure produce benefit, or is the benefit contingent on how it is used? Quote the evidence." },

  { id: "domain-variation", label: "domain variation: mobile, data pipelines, frontend, distributed",
    q: "Find authoritative, sourced guidance on how operational procedures differ across these software domains, and what stays constant:\n\n1. MOBILE APP RELEASES — app store review latency, phased/staged rollout mechanics, the fact that a shipped binary cannot be recalled, halting a rollout vs rolling back, forced-update mechanisms. Apple App Store Connect and Google Play Console official docs on staged rollout and halting.\n2. DATA PIPELINES / BATCH — backfill procedures, idempotency and re-run safety, partial-failure and poison-record handling, data-correctness verification after recovery, watermark/late-data handling. Look for Google/Netflix/Airbnb engineering docs and the dbt/Airflow operational guidance.\n3. FRONTEND / WEB — CDN cache invalidation, client-side caching meaning users hold broken code after a server fix, feature flags as the rollback mechanism, service worker traps.\n4. DISTRIBUTED BACKEND — the standard cloud case, for contrast.\n\nFor each, quote a real source on what its operational procedures must contain that others need not. Then state explicitly what is INVARIANT across all four." },

  { id: "cognitive-load-design", label: "information design for degraded readers",
    q: "Find evidence-based guidance on DOCUMENT DESIGN for readers under time pressure, fatigue, or stress — how to lay out a procedure so a degraded reader can execute it.\n\nSearch: cognitive load theory applied to instructional/technical documents (Sweller — split-attention effect, redundancy effect, worked-example effect, modality effect) and whether these transfer to procedural documents; plain language research and the US Plain Writing Act / plain-language.gov evidence base; typography and legibility research for emergency documents; the 'signal detection' and 'place-keeping' literature on losing your place in a procedure (Altmann & Trafton memory-for-goals, task interruption and resumption lag research — how long it takes to resume after an interruption and what cues help); and checklist place-keeping aids.\n\nSpecifically actionable: what reduces the chance a reader loses their place, misreads a step, or conflates two steps? What does the interruption-recovery literature say about resumption cues?" },

  { id: "alert-linkage", label: "alert-to-procedure linkage and diagnostic entry",
    q: "Find authoritative guidance on how a procedure is FOUND and ENTERED at the moment it's needed — the discoverability problem.\n\nSearch: Google SRE Book/Workbook on alert annotations and playbook links; Prometheus/Alertmanager conventions for runbook_url annotations; the OpenSlo / SLO alerting practice; PagerDuty and Grafana docs on runbook links in alerts; ITIL on known-error databases; and any research on time-to-locate-procedure as a component of incident duration.\n\nAlso: how should a runbook state its own TRIGGER/entry condition so the right procedure is selected under pressure, and how do practitioners avoid selecting the wrong procedure? Look for aviation guidance on QRH indexing and non-normal checklist selection, which is the same problem (choosing the right checklist for an ambiguous failure)." },

  { id: "agent-execution-safety", label: "AI agents executing operational procedures safely",
    q: "Find 2024-2026 guidance and research on AI AGENTS executing operational procedures, and on writing procedures that an agent will consume.\n\nSearch: Microsoft/Google/Amazon research on LLM agents in incident response (AIOps agent papers, RCACopilot, Nissist, StepFly, ITBench, AgentSRE); OpenAI/Anthropic guidance on agent safety and human-in-the-loop checkpoints for consequential actions; the concept of 'blast radius' or 'reversibility' gating for autonomous actions; NIST AI RMF as applied to operational automation; and any published framework for classifying which runbook steps an agent may execute autonomously vs which require human authorization.\n\nAlso: documented failure modes of LLM-generated technical instructions — hallucinated CLI flags, invented API parameters, outdated syntax, false numeric specificity. Any measurement of these rates.\n\nBe rigorous: report only what you can source, and say what you could not find." },
]

phase("Investigate")
log("Launching " + LINES.length + " parallel investigations")

const results = await pipeline(
  LINES,
  (line) => agent(
    "## Deep targeted investigation: " + line.label + "\n\n" + line.q + "\n\n" +
    "## Method\n" +
    "1. Run MULTIPLE WebSearches with varied phrasing. Do not stop at the first page of results.\n" +
    "2. WebFetch the actual primary sources. Do not report a claim from a search snippet alone.\n" +
    "3. For each finding, capture a VERBATIM quote from the source you fetched.\n" +
    "4. State the transferable authoring rule — technology-agnostic, applicable to a runbook in any language or domain. If a finding does not generalize, say 'none'.\n\n" +
    "## Standards\n" +
    "- Primary sources (standards bodies, regulators, official postmortems, peer-reviewed work) over vendor blogs and listicles.\n" +
    "- Numbers must be exact and attributed. No approximations presented as measurements.\n" +
    "- Distinguish what a source MANDATES from what it merely suggests. Preserve hedges ('should', 'can') — do not harden them.\n" +
    "- If you cannot source a thing, put it in nothingFound. An honest gap is worth more than a confident guess: this feeds a durable engineering standard.\n\n" +
    "Structured output only.",
    { label: "dig:" + line.id, phase: "Investigate", schema: FIND_SCHEMA }
  ).then(r => {
    if (!r) return null
    log(line.id + ": " + (r.findings || []).length + " findings" + (r.nothingFound ? " (+gaps noted)" : ""))
    return { line, r }
  }),

  (res) => {
    if (!res || !res.r.findings || res.r.findings.length === 0) return res
    const list = res.r.findings.map((f, i) =>
      "[" + i + "] CLAIM: " + f.claim + "\n    SOURCE: " + f.source + "\n    QUOTE: \"" + f.quote + "\"\n    STATED CONFIDENCE: " + f.confidence
    ).join("\n\n")
    return agent(
      "## Adversarial challenge\n\n" +
      "Another researcher produced these findings on: **" + res.line.label + "**\n" +
      "They are destined for a durable engineering-standards document. Your job is to find the ones that are WRONG.\n\n" +
      "## Findings under challenge\n" + list + "\n\n" +
      "## Method\n" +
      "For each finding: WebFetch the cited source and check that (a) the quote genuinely appears there, (b) the claim is a faithful reading and not a hardened or generalized one, (c) every number, date, and attribution is exactly right, (d) no contradicting or superseding source exists.\n" +
      "Then WebSearch for contradicting evidence on the central claims.\n\n" +
      "Put a claim in `killed` (with the reason appended after ' -- ') if the quote cannot be found, the claim overreaches it, a figure is wrong, or the attribution is mistaken.\n" +
      "Put it in `survives` ONLY if you independently confirmed it.\n" +
      "Be strict. A wrong claim in a standards document is worse than a missing one.\n\n" +
      "Structured output only.",
      { label: "challenge:" + res.line.id, phase: "Challenge", schema: CHALLENGE_SCHEMA }
    ).then(ch => ({ ...res, challenge: ch }))
  }
)

const clean = results.filter(Boolean)
log("Done: " + clean.length + " investigation lines completed")

return {
  lines: clean.map(x => ({
    id: x.line.id,
    label: x.line.label,
    findings: x.r.findings,
    nothingFound: x.r.nothingFound,
    challenge: x.challenge || null,
  })),
}