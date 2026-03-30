# Test Scenario: Personal Medication Tracker

## Scenario Overview

- **Primary structural:** `handles_sensitive_data` (health data: medications, dosages, compliance records)
- **Secondary structural:** `has_human_interface` (iOS mobile app)
- **Domain:** Health / Caregiving
- **Risk Level:** High
- **Purpose:** Tests `handles_sensitive_data` detection, data lifecycle design, privacy architecture, and proportionate regulatory awareness. Creates the hardest proportionality tension in the scenario set: health data demands serious privacy treatment, but this is a personal 2-user app, not a hospital records system. Tests emotional context calibration — the user is an anxious caregiver, not evaluating enterprise software.

## Why This Scenario Is Challenging

This scenario creates productive tension across multiple framework dimensions:

1. **High risk + low scale.** Health data is genuinely sensitive — medication information reveals diagnoses, conditions, and treatment plans. But this is a personal tool for one family, not a regulated healthcare platform. The framework must take the data seriously without prescribing HIPAA compliance infrastructure. This is the hardest proportionality test: being appropriately serious without being disproportionately heavy.

2. **Regulatory nuance.** HIPAA applies to covered entities (hospitals, insurers, providers), not personal apps. But the _principles_ behind HIPAA — minimum necessary data, encryption at rest, access controls, breach awareness — still apply. The framework should surface these principles without claiming HIPAA compliance is required. 

3. **Emotional context.** This user is worried about his father's health, not evaluating software architecture. He needs reassurance that the tool will be reliable and private — not a lecture on threat modeling. The framework must read the emotional room and adjust its tone. Questions about "breach scenarios" should feel like caring about his father's privacy, not conducting a security audit.

4. **Medication safety implications.** Push notification reminders are safety-critical: a missed reminder could mean a missed dose. The framework should surface this — notification reliability is not a UX convenience feature, it's a health concern. But it shouldn't catastrophize for a supplement-level risk product.

5. **iOS-native patterns.** Swift/iOS has specific patterns for health data: Keychain for secrets, Core Data or SwiftData for local persistence, UserNotifications for push, and Apple's own HealthKit as a potential integration point. The framework should adapt to this platform without prescribing it.

6. **Privacy-conscious user.** The user will actively push back on data collection ("why does this need location?"). The framework should demonstrate data minimization naturally, not defensively. This tests whether the system's privacy recommendations are genuine or performative.

7. **Degenerate characteristics.** This has no programmatic interface, no multiple party types, doesn't run unattended (reminders are push notifications from the OS, not a background daemon), and isn't distributed. The framework should correctly identify what this ISN'T, not just what it is.

## Test Persona

**Name:** David Okafor

**Background:** 38 years old, marketing manager at a mid-size consumer goods company. Lives 20 minutes from his father, who was recently diagnosed with early-stage Parkinson's disease. His father is now on 4 daily medications with different schedules (morning, with food, evening, bedtime). David's mother passed away two years ago, so he's the primary support. He visits twice a week but worries about the days he's not there.

**Technical expertise:**
- Uses apps fluently on his iPhone — banking, fitness, messaging
- Has followed online tutorials to customize a Notion workspace
- Has never written code and doesn't know what an API is
- Understands "the cloud" conceptually but couldn't explain client-server architecture
- Can evaluate apps as a user (good UX vs. bad UX) but not the technology behind them

**Communication style:**
- Speaks in terms of his father's daily routine, not technical features
- Anxious about reliability: "what if it doesn't send the reminder?"
- Privacy-protective: "I don't want his health data floating around"
- Emotional undertone — this isn't a fun project, it's about caring for his dad
- Appreciates reassurance but detects when it's hollow
- Will push back on unnecessary data collection

**Current motivation:** His father missed an evening dose last week because he fell asleep watching TV. David didn't find out until the next visit. He wants a simple way to track whether each dose was taken and get alerted if one is missed. He's looked at medication apps but they all want to create accounts, sync to the cloud, and ask for permissions he's not comfortable granting for his father's health data.

## Evaluation Procedure

### Setup

1. Create an isolated project directory for the evaluation:
   ```bash
   python3 tools/prawduct-setup.py setup /tmp/eval-medication-tracker --name "DoseCheck"
   ```

### Running the evaluation

3. Start a new LLM conversation in `/tmp/eval-medication-tracker`. The generated repo is self-contained (own CLAUDE.md, hooks, Critic instructions).
4. Send the Input prompt (below) as the user's opening message.
5. For each system question, respond using the scripted Test Conversation responses below. If the system asks about a topic not covered, respond in character as David Okafor (see Test Persona).
6. Let the system run through discovery → planning.

### Evaluating results

7. After the run completes, evaluate against the Evaluation Rubric (below) by checking:
   - `.prawduct/project-state.yaml` against the C5 criteria
   - `.prawduct/artifacts/*.md` against the C3 criteria
   - The conversation transcript against C1, C2, and C4 criteria
8. Record pass/fail for each must-do, must-not-do, and quality criterion.

### Recording results

9. **Before cleanup**, record evaluation results. Include: scenario name, date, framework version (git SHA), pass/fail per rubric criterion with evidence, and issues found.

### Cleanup

10. Delete the evaluation directory when done:
    ```bash
    rm -rf /tmp/eval-medication-tracker
    ```

## Input

> "I need to build an app to track my dad's medications. He has Parkinson's and takes 4 different pills at different times of day. I want to know if he took them and get a notification if he misses one. It needs to be on his iPhone and I want his health data to stay private — not synced to some company's server."

The input signals:
- Sensitive data (medications, health condition, diagnosis)
- Human interface (iPhone app)
- Privacy-first ("stay private", "not synced to some company's server")
- Emotional context (father with Parkinson's, caregiving)
- Non-technical user (describes behavior, not technology)
- Specific platform (iPhone)
- Safety-critical aspect (medication reminders)

## Test Conversation

To ensure repeatable evaluation, the following scripted responses define what David Okafor says when asked about each topic. The evaluator provides these responses regardless of how the system phrases its questions. If the system doesn't ask about a topic (e.g., because it infers the answer), the corresponding response is not volunteered.

**When asked to confirm classification or assumptions:**
> "Yeah, that's right."
>
> Accept reasonable inferences. Correct if the system misunderstands the caregiving context or privacy expectations.

**When asked about users / who uses the app:**
> "Mainly my dad — he'd use it on his iPhone to mark when he takes each pill. And me — I just want to get a notification if he misses one so I can call and remind him."

**When asked about medication details / what to track:**
> "He takes 4 medications right now. Each has a name, dosage, and time — like carbidopa-levodopa 25/100mg three times a day. I just need to log whether each dose was taken, and when."

**When asked about the reminder / notification flow:**
> "I'm thinking his phone buzzes at the scheduled time, he taps 'took it' or snoozes. If he doesn't respond within, say, 30 minutes, I get a notification on my phone."

**When asked about data storage / where data lives:**
> "On his phone. That's it. I don't want some cloud service storing his medication list. If we need to sync between his phone and mine, maybe iCloud — at least Apple encrypts that. But I'd rather keep it simple."

**When asked about sharing with doctors:**
> "Not right now. Maybe later it'd be nice to export a report for his neurologist, but that's not v1. Right now I just need to track compliance."

**When asked about what happens if the phone is lost or replaced:**
> "Good question. A backup would be nice — but encrypted. I'd rather lose the data than have it end up somewhere unprotected."

**When asked about privacy / data collection concerns:**
> "I don't want the app collecting anything it doesn't need. No location, no contacts, no usage analytics. Just the medication data. I looked at some apps and they all want permissions that make no sense for a pill tracker."

**When asked about history / how far back to keep records:**
> "A few months at least. Enough that when we see his doctor every 3 months, we can look at how consistent he's been."

**When asked about multiple medications changing over time:**
> "His medications will probably change as the disease progresses. I need to be able to add new ones and stop old ones without losing the history."

**When asked about accessibility / his father's ability to use the app:**
> "He's 71 and his hands shake sometimes — that's the Parkinson's. Big buttons, simple interface. He can use his iPhone fine for calls and texts, but nothing too fiddly."

**When asked about anything not covered above:**
> Give a brief answer consistent with the persona: a concerned, privacy-conscious caregiver who wants something simple and reliable for his father's medications. Emotional but not dramatic. Pushes back on unnecessary complexity or data collection.

**General persona:** Concerned, privacy-protective, non-technical. Describes needs through his father's daily routine. Wants simplicity and reliability above all. Will push back on scope creep or unnecessary data access.

## Evaluation Rubric

### Discovery (C2)

**Must-do:**

- `[simulation]` Detect `handles_sensitive_data` (health data: medications, dosages, compliance records, diagnostic information).
- `[simulation]` Detect `has_human_interface` (iOS mobile app).
- `[simulation]` Assign high risk (health data, medication safety, privacy requirements).
- `[simulation]` Classify domain as health or caregiving.
- `[interactive]` Surface data privacy as a primary concern, not an afterthought.
- `[interactive]` Surface data lifecycle: where health data is stored, who can access it, what happens on device loss.
- `[interactive]` Surface encryption at rest as a structural requirement for health data.
- `[interactive]` Surface medication reminder reliability as a safety concern (not just a UX feature).
- `[interactive]` Surface accessibility needs (father has Parkinson's tremor, needs large touch targets).
- `[interactive]` Probe regulatory context proportionately — acknowledge health data sensitivity without claiming HIPAA compliance is required for a personal app.
- `[simulation]` Limit total discovery questions to 10-15 for this high-risk product.

**Must-not-do:**

- `[interactive]` Must not prescribe enterprise HIPAA compliance infrastructure for a personal family app.
- `[interactive]` Must not ask about multi-user enterprise features, admin panels, or organizational deployment.
- `[interactive]` Must not ask about monetization or subscription models.
- `[interactive]` Must not suggest cloud sync as the default data strategy when the user explicitly said local-only.
- `[interactive]` Must not ask the user to evaluate encryption algorithms or key management strategies.
- `[interactive]` Must not be dismissive of the user's privacy concerns ("most apps handle this fine").
- `[interactive]` Must not treat the emotional context as irrelevant to design decisions.
- `[simulation]` Must not generate more than 18 discovery questions total.

**Quality criteria:**

- `[interactive]` Privacy concerns are validated, not challenged or minimized.
- `[interactive]` The system demonstrates data minimization naturally: "Since we only need medication names, dosages, and timestamps, I won't collect anything else — no location, no contacts, no analytics."
- `[interactive]` Regulatory nuance is correct: the system distinguishes between HIPAA requirements (for covered entities) and privacy best practices (for all health data), landing on the latter.
- `[interactive]` The emotional context is acknowledged: the system reads that this is about caring for a parent, not building a product, and calibrates tone accordingly.
- `[interactive]` Accessibility is raised in terms of the father's specific condition (tremor, age), not as a generic WCAG checklist.
- `[interactive]` Questions are ordered by impact — privacy and reliability before nice-to-have features.

### Session Management (C1)

**Must-do:**

- `[interactive]` Progress through discovery → planning without excessive back-and-forth.
- `[interactive]` Detect non-technical user from input style and vocabulary.
- `[interactive]` Adjust vocabulary — no unexplained jargon. "Encryption at rest" becomes "the data is scrambled on the phone so even if someone gets the phone they can't read it."
- `[interactive]` Confirm classification in plain language.
- `[interactive]` Read the emotional context and calibrate tone (reassuring, not clinical).
- `[interactive]` Make reasonable assumptions and state them explicitly.

**Must-not-do:**

- `[interactive]` Must not conduct more than 3-4 rounds of discovery for this product despite high risk — the user's patience is limited by emotional context.
- `[interactive]` Must not use clinical security terminology without explanation.
- `[interactive]` Must not ask the user to make decisions outside their expertise.
- `[interactive]` Must not treat high risk as requiring exhaustive interrogation — proportionate depth, not maximum depth.

**Quality criteria:**

- `[interactive]` Discovery completes in 3-4 question rounds despite high risk.
- `[interactive]` The user feels heard and reassured, not audited.
- `[interactive]` Assumptions about privacy architecture are stated clearly enough that the user can confirm they match expectations.
- `[interactive]` Transitions between topics feel natural and empathetic.

### Planning (C3)

**Must-do (universal artifacts):**

- `[simulation]` Produce universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, observability strategy, dependency manifest.
- `[simulation]` All artifacts have correct YAML frontmatter with dependency declarations.

**Must-do (sensitive data deepening):**

- `[simulation]` Security model is deepened beyond the standard template: includes data lifecycle (creation → storage → access → deletion), encryption at rest specification, device-loss scenario, data minimization principles.
- `[simulation]` Data model explicitly marks which fields contain sensitive data and specifies their storage protection (encrypted at rest, never transmitted unencrypted).
- `[simulation]` Security model addresses: local-only storage rationale, Keychain for sensitive identifiers, encrypted backup strategy, what data is exposed in notifications (no medication names in lock screen previews).
- `[simulation]` Test specifications include privacy and security tests: data encrypted at rest, no sensitive data in logs, notification text doesn't reveal medication details, data deletion actually removes data.

**Must-do (human-interface artifacts):**

- `[simulation]` Produce human-interface artifacts proportionate to a high-risk personal health app.
- `[simulation]` Screen specs address accessibility for a user with Parkinson's tremor: large touch targets, minimal fine-motor requirements, high contrast, simple navigation.
- `[simulation]` Onboarding spec is simple: medication entry flow that a 71-year-old can complete (or that David can do for his father).

**Must-do (content quality):**

- `[simulation]` Data model includes at minimum: Medication (name, dosage, schedule, active/inactive status), DoseEvent (timestamp, taken/missed/snoozed), ReminderConfiguration, NotificationRecord.
- `[simulation]` NFRs address notification reliability as a safety concern (not just a UX metric): what is the acceptable delay for a "missed dose" alert?
- `[simulation]` Operational spec is simple (single device, no server) but addresses backup, restore, and device migration.
- `[simulation]` Dependency manifest reflects iOS-native choices: no unnecessary third-party SDKs, preference for system frameworks.

**Must-not-do:**

- `[simulation]` Must not generate API artifacts (no programmatic interface).
- `[simulation]` Must not generate multi-party artifacts (David and his father are the same party type — family caregivers, not distinct roles with different trust levels).
- `[simulation]` Must not generate automation/pipeline artifacts.
- `[simulation]` Must not specify a backend server or cloud database.
- `[simulation]` Must not over-engineer: no FHIR compliance, no HL7 integration, no audit trail infrastructure for a personal app.
- `[simulation]` Must not under-engineer: health data encryption at rest is non-negotiable regardless of scale.

**Quality criteria:**

- `[simulation]` Security model reflects genuine understanding of health data privacy, not boilerplate "encrypt everything."
- `[simulation]` The distinction between "personal health app privacy" and "HIPAA compliance" is clear in the artifacts.
- `[simulation]` Data lifecycle is traceable: a reader can follow medication data from entry through storage through deletion.
- `[simulation]` Test specifications include at least 2 concrete privacy-specific tests (e.g., "medication names do not appear in push notification preview text").
- `[simulation]` Accessibility specifications are specific to the user's condition (tremor), not generic WCAG compliance.
- `[simulation]` Artifacts are proportionate: security model is thorough for privacy but doesn't read like a SOC 2 audit plan.

### Review Perspectives (C4)

**Must-do:**

- `[simulation]` Product perspective: confirms this solves a real caregiving problem; scope is appropriate for a personal tool.
- `[simulation]` Design perspective: raises accessibility for Parkinson's tremor (touch target size, gesture complexity), notification UX (lock screen privacy, snooze flow), and the caregiver alert flow.
- `[simulation]` Architecture perspective: raises local-only storage implications (backup, device migration, no server-side recovery), encryption approach, and notification delivery reliability.
- `[simulation]` Skeptic perspective: raises at least one realistic concern (e.g., what if the father's phone dies and David isn't notified? What if medication schedules change and old reminders fire? What about time zones if David travels?).
- `[simulation]` At least one perspective specifically addresses health data privacy risks (data exposure vectors, notification content, backup encryption).
- `[simulation]` Each finding has a specific recommendation and severity level.

**Must-not-do:**

- `[simulation]` Must not raise enterprise healthcare concerns (HIPAA certification, third-party audit, PHI handling infrastructure).
- `[simulation]` Must not produce vague findings ("consider the privacy implications").
- `[simulation]` Must not block on concerns disproportionate to a personal family app.
- `[simulation]` Must not dismiss privacy concerns as paranoid or over-cautious.

**Quality criteria:**

- `[simulation]` Findings are specific and actionable.
- `[simulation]` Severity ratings reflect that privacy failures for health data are more serious than for utility apps (a privacy finding here should be WARNING or BLOCKING, not NOTE).
- `[simulation]` At least one finding addresses the safety dimension (medication reminder reliability).
- `[simulation]` Findings demonstrate empathy for the caregiving context, not just technical correctness.

### Project State (C5)

**Must-do (structural):**

- `[simulation]` All populated fields use correct types per the template schema.
- `[simulation]` No fields added that don't exist in the template schema.
- `[simulation]` Risk factors include rationale.

**Must-do (content after discovery → planning):**

- `[simulation]` `classification.structural.handles_sensitive_data`: not null, identifying health/medication data as the sensitive data type.
- `[simulation]` `classification.structural.has_human_interface`: not null, with modality "screen" and platform indicating iOS/mobile.
- `[simulation]` `classification.structural.has_multiple_party_types`: null or false (single family unit, not distinct party types).
- `[simulation]` `classification.structural.runs_unattended`: null or false (push notifications are OS-managed, not a background daemon).
- `[simulation]` `classification.domain`: populated ("health", "caregiving", or "personal health").
- `[simulation]` `classification.risk_profile.overall`: "high".
- `[simulation]` `classification.risk_profile.factors`: at least 3 factors with rationale (health data sensitivity, medication safety, privacy requirements, elderly user accessibility).
- `[simulation]` `product_definition.vision`: specific one-sentence description mentioning medication tracking and caregiver alerts.
- `[simulation]` `product_definition.users.personas`: at least 1 persona capturing the father (primary user) and David (caregiver/monitor).
- `[simulation]` `product_definition.core_flows`: at least 3 flows (log dose, receive reminder, caregiver missed-dose alert).
- `[simulation]` `product_definition.scope.v1`: includes medication entry, scheduled reminders, dose logging, caregiver notification.
- `[simulation]` `product_definition.scope.later`: at least 2 deferred items (e.g., doctor report export, medication interaction checking, HealthKit integration).
- `[simulation]` `product_definition.platform`: populated (iOS/iPhone).
- `[simulation]` `technical_decisions`: includes data storage approach (local, encrypted) and notification mechanism, each with rationale.
- `[simulation]` `design_decisions.accessibility_approach`: populated, mentioning Parkinson's tremor and large touch targets.
- `[simulation]` `design_decisions.error_handling_approach`: addresses notification failure as a safety concern.
- `[simulation]` `user_expertise`: `technical_depth` at beginner or novice level.

**Must-not-do:**

- `[simulation]` Must not set risk below "high" given health data sensitivity.
- `[simulation]` Must not add `exposes_programmatic_interface` or `multi_process_or_distributed`.
- `[simulation]` Must not set `runs_unattended` to true for OS-managed push notifications.

**Quality criteria:**

- `[simulation]` A reader of `project-state.yaml` alone can understand: this is an iOS medication tracker for an elderly Parkinson's patient, with caregiver alerts, local-only encrypted storage, and high privacy requirements.
- `[simulation]` Values are specific, not generic ("medication compliance tracker for elderly Parkinson's patient with caregiver alerting" not "a health application").
- `[simulation]` Risk factors specifically cite health data, not generic "data sensitivity."

## End-to-End Success Criteria

The scenario succeeds when:

1. Starting from the input above, the system correctly detects `handles_sensitive_data` (health/medication data) and `has_human_interface` (iOS).
2. Discovery surfaces data privacy as a primary concern, including data lifecycle, encryption at rest, notification privacy, and device-loss scenarios.
3. The system correctly distinguishes between HIPAA requirements (not applicable to a personal app) and privacy best practices (absolutely applicable).
4. Medication reminder reliability is surfaced as a safety concern, not just a UX feature.
5. Universal artifacts are generated with correct frontmatter. Security model and data model are deepened for sensitive data (encryption, data lifecycle, privacy-specific test cases).
6. Human-interface artifacts address accessibility for a user with Parkinson's tremor (large touch targets, minimal fine-motor requirements).
7. NO API, multi-party, automation, or server-side artifacts are generated.
8. Vocabulary throughout is calibrated for a non-technical, emotionally-invested caregiver.
9. The total output is proportionate — serious about health data privacy without prescribing enterprise compliance infrastructure for a 2-user family app.
10. A developer reading the artifacts could build an iOS medication tracker with appropriate privacy protections, understanding exactly what data is sensitive, how it must be protected, and why.
