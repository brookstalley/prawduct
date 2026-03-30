# Test Scenario: Background Data Pipeline

## Scenario Overview

- **Primary structural:** `runs_unattended` (trigger: scheduled); **Domain characteristics:** external service integration (RSS feeds, Slack API)
- **Domain:** Productivity / Content Curation
- **Risk Level:** Low-Medium
- **Purpose:** Tests `runs_unattended` structural characteristic detection, operational-first discovery, and verification that the system does NOT ask about UIs, screens, or navigation for headless systems. Tests technical user calibration and dynamic domain depth for external integrations.

## Test Persona

**Name:** Alex Chen

**Background:** Solo indie developer running a weekly tech newsletter as a side project (500 subscribers). Mid-level backend developer at a startup during the day. Has coding skills but hasn't built automation/pipeline systems before. No ops/SRE background.

**Technical expertise:**
- Comfortable with APIs, webhooks, RSS feeds, basic scripting
- Understands technical terminology but not an expert in infrastructure/operations
- Hasn't thought deeply about monitoring, alerting, failure recovery
- Cost-conscious (side project budget)

**Communication style:**
- Direct and practical
- Uses technical terms comfortably but doesn't over-engineer
- Cooperative but will push back if something seems excessive
- Focused on time-saving and reliability

**Current pain:** Spends 2-3 hours every Sunday manually browsing tech sites and curating articles for the newsletter. Wants to automate the discovery and initial filtering, then review and send manually.

## Evaluation Procedure

### Setup

1. Create an isolated project directory for the evaluation:
   ```bash
   python3 tools/prawduct-setup.py setup /tmp/eval-background-pipeline --name "Digest Bot"
   ```

### Running the evaluation

3. Start a new LLM conversation in `/tmp/eval-background-pipeline`. The generated repo is self-contained (own CLAUDE.md, hooks, Critic instructions).
4. Send the Input prompt (below) as the user's opening message.
5. For each system question, respond using the scripted Test Conversation responses below. If the system asks about a topic not covered, respond in character as Alex Chen (see Test Persona).
6. Let the system run through discovery → planning.

### Evaluating results

7. After the run completes, evaluate against the Evaluation Rubric (below) by checking:
   - `/tmp/eval-background-pipeline/.prawduct/project-state.yaml` against the C5 criteria
   - `/tmp/eval-background-pipeline/.prawduct/artifacts/*.md` against the C3 criteria
   - The conversation transcript against C1, C2, and C4 criteria
8. Record pass/fail for each must-do, must-not-do, and quality criterion.

### Recording results

9. **Before cleanup**, record evaluation results. Include: scenario name, date, framework version (git SHA), pass/fail per rubric criterion with evidence, and issues found.

### Cleanup

10. Delete the evaluation directory when done:
    ```bash
    rm -rf /tmp/eval-background-pipeline
    ```

## Input

> "I want to build something that monitors a handful of RSS feeds and tech sites every morning, filters for interesting articles based on topics I care about, and posts a summary to my Slack workspace. Right now I waste 2-3 hours every week doing this manually."

The input signals:
- Automation/pipeline (scheduled, unattended operation)
- Technical user (comfortable with RSS, Slack, webhooks)
- Clear pain point (time waste)
- Filtering logic requirement
- External integrations (RSS sources, Slack)

## Test Conversation

To ensure repeatable evaluation, the following scripted responses define what Alex Chen says when asked about each topic. The evaluator provides these responses regardless of how the system phrases its questions. If the system doesn't ask about a topic (e.g., because it infers the answer), the corresponding response is not volunteered.

**When asked to confirm classification or assumptions:**
> "Yeah, that's right."
>
> Accept reasonable inferences. Correct if the system makes a wrong assumption.

**When asked about data sources / which feeds:**
> "I follow maybe 10-12 sources — Hacker News, a few subreddits via RSS, some individual blogs, Techmeme. The exact list might change over time."

**When asked about filtering criteria / what makes an article "interesting":**
> "I care about developer tools, AI/ML stuff, and indie hacking. Not interested in enterprise IT news or most cryptocurrency stuff. I'd like to tune the filtering over time as I see what it picks."

**When asked about scheduling / how often to run:**
> "Once a day in the morning would be good. Maybe 7 AM Pacific so I can review before my workday starts."

**When asked about output format / what goes to Slack:**
> "Just post a list of article titles and links to a dedicated channel. Maybe group by source or topic if that makes sense. Nothing fancy."

**When asked about false positives/negatives / filtering accuracy:**
> "I'd rather see some irrelevant stuff than miss important articles. It's fine if I have to skip a few."

**When asked about failure scenarios / what happens if it breaks:**
> "I guess if it fails silently and I just don't get my digest one day, that would be annoying. I wouldn't know if there was really nothing new or if it broke."

**When asked about cost / infrastructure:**
> "I don't want to spend much on this. It's a side project. If there's a free tier option that works, I'd prefer that."

**When asked about current process / how they do it now:**
> "I open a bunch of tabs every Sunday, skim headlines, copy the good ones into a doc, then write up the newsletter from there. It's tedious."

**When asked about change frequency / how often the logic needs updating:**
> "Probably tweak the topic filters every few weeks as my interests shift. The source list changes maybe once a month."

**When asked about what to call the pipeline:**
> "I've been calling it 'morning digest' in my head. Something like 'digest-bot' or 'feed-filter' would work too. Not picky about the name."

**When asked about access / who needs to configure or maintain this:**
> "Just me. Nobody else needs to touch it."

**When asked about anything not covered above:**
> Give a brief, practical, technically-informed answer consistent with Alex Chen's persona. Focus on pragmatism and time-saving. Avoid over-engineering. Express mild concern about reliability but trust the system's recommendations on operational topics.

**General persona behavior:**
- Uses technical terminology naturally (API, webhook, RSS, cron job, etc.)
- Pragmatic about trade-offs (cost vs. features, simplicity vs. robustness)
- Hasn't thought deeply about monitoring or failure recovery — will defer to system expertise here
- Cost-sensitive but willing to pay a bit for reliability
- Cooperative, responds concisely, doesn't volunteer unnecessary detail

## Evaluation Rubric

### Discovery (C2)

**Must-do:**

- `[simulation]` Detect `runs_unattended` structural characteristic (trigger: scheduled). Must NOT detect `has_human_interface`. Must identify external service integration (RSS feeds, Slack API) as a domain characteristic.
- `[simulation]` Classify domain as Productivity or Content Curation (or similar).
- `[simulation]` Assign low-medium risk profile (operational failure matters, but impact is limited — affects one person's side project, not a business-critical system).
- `[interactive]` Ask about data sources and their reliability.
- `[interactive]` Ask about filtering/processing logic.
- `[interactive]` Ask about failure scenarios and how failures should be surfaced.
- `[interactive]` Ask about scheduling/trigger frequency.
- `[interactive]` Ask about cost sensitivity or infrastructure constraints.
- `[interactive]` Surface monitoring and alerting as a consideration (pipeline runs unattended — how do you know it's working?).
- `[interactive]` Surface error handling approach using infer-confirm-proceed. For a low-medium risk unattended pipeline, this should go beyond "standard patterns" — at minimum surface recoverable vs. fatal errors and what happens on failure (retry? skip? alert?).
- `[interactive]` Surface configuration management (filter criteria will change over time — how is that handled?).
- `[interactive]` Limit total discovery questions to 8-12 for this risk level (more than low-risk family utility, fewer than a high-risk B2B platform).

**Must-not-do:**

- `[simulation]` Must not detect `has_human_interface` structural characteristic.
- `[interactive]` Must not ask about screens, navigation, user flows, or UI design.
- `[interactive]` Must not ask about onboarding experience, accessibility, or visual design.
- `[interactive]` Must not ask about authentication or user authorization (single-user automation).
- `[interactive]` Must not ask about real-time interactivity or multi-user collaboration.
- `[interactive]` Must not ask about API contracts or external consumers (the pipeline consumes APIs but doesn't expose one).
- `[interactive]` Must not recommend not building (this is a clear, solvable problem).
- `[interactive]` Must not spend more than 2 turns researching existing RSS aggregation tools.
- `[interactive]` Must not generate more than 15 discovery questions total.

**Quality criteria:**

- `[hybrid]` Questions prioritize operational concerns (failure modes, monitoring, cost) over feature details.
- `[interactive]` Questions recognize user's technical competence (use appropriate terminology, don't over-explain basics).
- `[interactive]` Questions surface considerations user hasn't raised (alerting, silent failure, rate limits from sources, cost of LLM-based filtering if applicable).
- `[hybrid]` Inferences are made about technical choices the user hasn't specified (deployment target, data storage) and confirmed.
- `[hybrid]` Prior art awareness surfaces relevant tools (RSS aggregators, existing feed-to-Slack solutions) and key libraries as expertise. Acknowledges alternatives exist but respects Alex's choice to build a custom solution. For low-medium risk, 2-3 searches covering solutions and relevant libraries is proportionate.
- `[interactive]` **Challenge Gently, Defer Gracefully (Principle 22):** If the technical user names a specific technology as the solution (e.g., "just use Kafka for this"), the system should challenge proportionately — explaining why the simpler approach may suffice for a side project and offering the general principle, while deferring if the user insists.

### Session Management (C1)

**Must-do:**

- `[hybrid]` Progress through stages 0 → 0.5 → 1 → 2 without excessive back-and-forth (partially evaluable: change_log shows stage transitions).
- `[hybrid]` Infer technical user from input vocabulary (RSS, Slack, pipeline, monitoring).
- `[interactive]` Use technical terminology appropriately (don't avoid it, but don't assume deep ops expertise either).
- `[interactive]` Confirm classification in clear language: "This is an automation pipeline that runs on a schedule, not something with a user interface. Sound right?"
- `[hybrid]` Make reasonable assumptions about technical choices (deployment, infrastructure, storage) and state them explicitly.
- `[hybrid]` Recognize when discovery is "good enough" — this is a medium-complexity automation, not a critical system (partially evaluable: question count and artifact completeness visible in outputs).

**Must-not-do:**

- `[hybrid]` Must not conduct more than 3-4 rounds of discovery questions for this risk level (partially evaluable: change_log entries and question count in project-state).
- `[interactive]` Must not over-explain basic technical concepts (RSS, webhooks, cron jobs) to a technical user.
- `[interactive]` Must not ask the user to choose between infrastructure options they haven't researched (AWS vs. GCP vs. DigitalOcean — system should make a recommendation with rationale).
- `[hybrid]` Must not skip operational concerns because the product is "just a side project."

**Quality criteria:**

- `[interactive]` Vocabulary matches user's technical level (technical but pragmatic, not enterprise-ops speak).
- `[interactive]` Discovery completes in 2-4 question rounds for low-medium risk.
- `[hybrid]` Operational concerns (monitoring, failure recovery, cost) are raised proactively, not only when user asks (partially evaluable: artifact content covers operational topics).
- `[interactive]` Phase transitions are natural and clearly communicated.

### Planning (C3)

**Must-do:**

- `[simulation]` Produce all 7 universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, dependency manifest.
- `[simulation]` Produce automation-specific artifacts: pipeline architecture, scheduling spec, monitoring/alerting spec, failure recovery spec, configuration spec.
- `[simulation]` All artifacts have correct YAML frontmatter with dependency declarations.
- `[simulation]` Pipeline architecture includes: data sources (RSS feeds, sites), processing stages (fetch, filter, format), output (Slack posting), scheduling trigger.
- `[simulation]` Data model includes: Article entity (title, URL, source, timestamp, topics), FilterCriteria entity (topics of interest, exclusions), perhaps SourceFeed entity.
- `[simulation]` Security model addresses: Slack webhook authentication, RSS source trust (malicious feeds?), rate limiting to external services. Proportionate to risk (no enterprise auth needed).
- `[simulation]` Test specifications include concrete scenarios for each pipeline stage: "Given feed X returns articles A, B, C and filter criteria includes topic Y, verify only articles matching Y are selected." Include failure scenarios: "Given feed X is unreachable, verify pipeline logs error and continues with other feeds."
- `[simulation]` NFRs include: cost constraints (free tier preferred), runtime performance (morning digest ready by 7 AM), and acceptable latency for Slack posting.
- `[simulation]` Operational spec includes: deployment target (likely serverless function or cron job on cheap VPS), monitoring (how to detect silent failure), alerting (where to send alerts — probably Slack itself or email), failure recovery (retry logic, dead letter handling).
- `[simulation]` Monitoring/alerting spec defines at least 3 alert conditions with specific triggers, thresholds, and notification channels — what metrics matter (successful runs, article count per run, feed fetch failures, filter match rate), what constitutes alertable failure.
- `[simulation]` Failure recovery spec addresses: individual feed failure (continue with others), Slack API failure (retry? queue for later?), filtering service failure, partial failures.
- `[simulation]` Configuration spec addresses: how filter criteria and source list are updated (config file? environment variables? simple admin UI?).
- `[simulation]` Dependency manifest includes: RSS parsing library, Slack API/webhook client, LLM API if used for filtering, cron/scheduler, and justifications.

**Must-not-do:**

- `[simulation]` Must not generate UI-specific artifacts (IA, screen specs, design direction, accessibility, onboarding).
- `[simulation]` Must not generate API/Service artifacts (API contracts, integration guide, versioning strategy, SLA definition).
- `[simulation]` Must not generate multi-party artifacts.
- `[simulation]` Must not over-engineer the security model (no user auth, no complex authorization).
- `[simulation]` Must not specify enterprise-grade operational requirements disproportionate to a side project (99.99% uptime SLA, 24/7 on-call, multi-region redundancy).

**Quality criteria:**

- `[simulation]` Artifacts are internally consistent (entities in data model appear in test specs, pipeline architecture stages match test scenarios).
- `[simulation]` Cross-references between artifacts are accurate.
- `[simulation]` Monitoring spec includes at least 3 named metrics with alert conditions; failure recovery spec covers at least 3 failure modes with specific recovery actions (e.g., "alert when no articles posted for 2 consecutive days" not "implement monitoring").
- `[simulation]` A coding agent reading these artifacts could build the pipeline without ambiguity about what happens in each failure mode.
- `[simulation]` Total artifact pages 8-15 for low-medium risk; automation-specific artifacts (pipeline architecture, scheduling, monitoring, failure recovery, configuration) each 1-3 pages.

### Review Perspectives (C4)

**Must-do:**

- `[simulation]` Product perspective: confirms this solves a real problem (manual curation is tedious), scope is appropriate (single-user automation is right-sized).
- `[simulation]` Design perspective: acknowledges this is a headless pipeline and evaluates configuration UX (how does Alex tune filters?) and output format (Slack message clarity). Does NOT evaluate screens/navigation/visual design.
- `[simulation]` Architecture perspective: evaluates pipeline stages (fetch, filter, post), failure isolation (one feed failure shouldn't kill whole run), and deployment choice (serverless vs. cron job trade-offs).
- `[simulation]` Skeptic perspective: raises at least one realistic concern. Examples: "What happens if a feed changes format and parsing breaks?" "How do you know if the filter criteria are too restrictive and you're missing good content?" "What if Slack's API rate limits you?"
- `[simulation]` Each finding has a specific recommendation, not just an observation.
- `[simulation]` Each finding has a severity level (blocking / warning / note).

**Must-not-do:**

- `[simulation]` Must not raise UI/UX concerns about screens or navigation (there are none).
- `[simulation]` Must not raise concerns about multi-user access or collaboration features (single user).
- `[simulation]` Must not block on concerns disproportionate to the risk level (this is a side project, not infrastructure).
- `[simulation]` Must not produce vague findings ("consider edge cases").

**Quality criteria:**

- `[simulation]` Findings are specific and actionable.
- `[simulation]` Operational findings are concrete (e.g., "monitoring spec doesn't address how to detect when all feeds are timing out simultaneously").
- `[simulation]` Severity ratings are proportionate to the product's risk level.
- `[simulation]` Addressing the findings would measurably improve the artifacts.
- `[simulation]` Total findings in the 8-15 range for low-medium risk (more than low-risk family utility, fewer than a high-risk platform).

### Project State (C5)

The rubric evaluates the resulting `project-state.yaml` after the full process (discovery → definition).

**Must-do (structural):**

- `[simulation]` All populated fields use correct types per the template schema.
- `[simulation]` No fields added that don't exist in the template schema.
- `[simulation]` Risk factors include rationale, not just a level.

**Must-do (content after discovery → definition):**

- `[simulation]` `classification.domain`: populated ("productivity" or "content-curation" or similar).
- `[simulation]` `classification.structural.runs_unattended`: not null, with trigger "scheduled".
- `[simulation]` `classification.structural.has_human_interface`: null (this is a headless system).
- `[simulation]` `classification.domain_characteristics`: includes external service integration (RSS feeds, Slack API).
- `[simulation]` `classification.risk_profile.overall`: "low" or "medium" (either is acceptable with rationale).
- `[simulation]` `classification.risk_profile.factors`: at least 3 evaluated factors with rationale. Must include operational factors (failure impact, cost of operation, silent failure risk) not just user-facing factors.
- `[simulation]` `product_definition.vision`: a clear, specific one-sentence description.
- `[simulation]` `product_definition.users.personas`: at least one persona (Alex Chen or equivalent).
- `[simulation]` `product_definition.core_flows`: replaced by or adapted to pipeline stages (data fetch, filtering, output posting) — at least 3 stages.
- `[simulation]` `product_definition.scope.v1`: at least 4 concrete items (basic filtering, Slack posting, error logging, configurable sources).
- `[simulation]` `product_definition.scope.later`: at least 1 item explicitly deferred (e.g., web UI for configuration, multiple output channels, ML-based filtering).
- `[simulation]` `product_definition.platform`: populated with deployment target (serverless, VPS, cloud function).
- `[simulation]` `product_definition.nonfunctional`: at least performance, cost, and uptime populated. Proportionate to risk (not 99.99% uptime for a side project).
- `[simulation]` `technical_decisions`: at least deployment target, data storage (if any — might be stateless), scheduling mechanism, and Slack integration approach. Each with rationale.
- `[simulation]` `user_expertise`: at least `technical_depth` (medium-high), `product_thinking`, and `operational_awareness` inferred with evidence.
- `[simulation]` `current_stage`: "definition" or later.
- `[simulation]` `change_log`: at least 1 entry (initial classification).

**Must-not-do:**

- `[simulation]` Must not detect `has_human_interface` structural characteristic.
- `[simulation]` Must not leave `classification.structural` with no active structural characteristics after initial classification.
- `[simulation]` Must not add UI/UX design decisions (no screens to design).
- `[simulation]` Must not set `risk_profile.overall` above "medium" for this scenario.

**Quality criteria:**

- `[simulation]` A reader of `project-state.yaml` alone can understand this is a background automation pipeline, not a UI application.
- `[simulation]` Values are specific, not generic ("daily RSS feed aggregation and filtering for tech newsletter curation" not "an automation product").
- `[simulation]` Scope decisions reflect the test conversation (basic filtering in v1, ML-based filtering deferred).
- `[simulation]` Operational considerations are captured in technical decisions (monitoring, failure handling, scheduling).

## End-to-End Success Criteria

The scenario succeeds when:

1. `[simulation]` The system correctly detects `runs_unattended` structural characteristic and identifies external service integration as a domain characteristic, NOT `has_human_interface`.
2. `[interactive]` Discovery focuses on operational concerns (failure modes, monitoring, cost, scheduling) rather than UI/UX concerns.
3. `[simulation]` Automation-specific artifacts (pipeline architecture, scheduling spec, monitoring/alerting spec, failure recovery spec, configuration spec) are generated.
4. `[simulation]` UI-specific artifacts (IA, screen specs, design direction, accessibility, onboarding) are NOT generated.
5. `[hybrid]` The system calibrates to a technical user (appropriate vocabulary, doesn't over-explain basics, but still surfaces operational expertise Alex lacks).
6. `[simulation]` Review Perspectives evaluate operational concerns (failure isolation, monitoring effectiveness, configuration management) rather than UI/UX concerns.
7. `[hybrid]` Total artifact count is 12-17 (7 universal + 5 automation-specific) with total pages 8-15 — more thorough than the low-risk family utility, but not as heavyweight as a business-critical system.
8. `[simulation]` A coding agent reading the output would have a clear, unambiguous plan for building a reliable background pipeline with proper monitoring and failure handling.
