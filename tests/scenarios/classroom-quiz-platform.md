# Test Scenario: Classroom Quiz Platform

## Scenario Overview

- **Primary structural:** `has_multiple_party_types` (teachers and students with different privileges and experiences)
- **Secondary structural:** `has_human_interface` (web application)
- **Borderline structural:** `handles_sensitive_data` (student records, users potentially under 13)
- **Domain:** Education
- **Risk Level:** Medium
- **Purpose:** Tests `has_multiple_party_types` detection, per-party flow design, trust boundary analysis, and data isolation. Tests whether the framework probes for age-related data sensitivity (COPPA) without interrogating a non-technical user. Tests vocabulary calibration for an educator who uses pedagogical rather than technical language.

## Why This Scenario Is Challenging

This scenario creates productive tension across multiple framework dimensions:

1. **Two genuinely distinct experiences.** Teachers and students don't just have different permissions — they have completely different workflows, screens, and mental models. The teacher creates content and analyzes results; the student consumes content and sees only their own performance. The framework must generate per-party specs that reflect this asymmetry, not a single user flow with permission checks.

2. **Trust boundary complexity.** Teachers see all student results; students see only their own. Students cannot see each other's scores. The join-code mechanism creates a trust boundary (who can enter a classroom?). These are real data isolation requirements the framework must surface, not just "add role-based access control."

3. **Borderline sensitive data.** Students may be under 13 (the persona is a middle school teacher). This borders on `handles_sensitive_data` due to COPPA implications. The framework should probe for student ages and surface the regulatory concern — but proportionately, not with an enterprise compliance checklist. A classroom tool is not a hospital records system.

4. **Non-technical educator vocabulary.** The user says "formative assessment" not "quiz endpoint," "differentiated learning" not "conditional rendering," "Chromebook" not "web client." The framework must calibrate vocabulary to the user without dumbing down the technical design. Questions should land in the user's domain language.

5. **Real-time vs. async tension.** "Students take quizzes in real-time in class" implies WebSocket or polling for live results, but this is a teacher's mental model — the actual technical requirement might be simpler. The framework should clarify the real-time need without forcing the user to make architecture decisions.

6. **Proportionality for education.** This is a classroom tool, not an EdTech platform. The framework should not suggest learning analytics dashboards, LMS integration, or gamification unless the user signals interest. But the multi-party and data sensitivity concerns are real and shouldn't be trivialized.

7. **Platform constraints.** School devices (Chromebooks, iPads) have specific constraints: no app installs, browser-only, possibly restricted networks. The framework should surface this from the education context without interrogating.

## Test Persona

**Name:** Priya Chandran

**Background:** 8th-grade science teacher at a public middle school, 15 years of teaching experience. Uses Google Classroom daily and is comfortable with educational technology but has never built software. Has a clear pedagogical vision — uses quizzes as formative assessment (to check understanding during a lesson, not just for grades). Frustrated that existing quiz tools either cost money per student or don't give her the real-time feedback she wants during class.

**Technical expertise:**
- Fluent with educational software (Google Classroom, Kahoot, Quizlet) as a user
- Understands the concept of "an app" and "a website" but not the difference between frontend and backend
- Cannot evaluate technical alternatives (React vs. Vue means nothing to her)
- Has strong opinions about the student experience from years of classroom observation
- Knows exactly what data she needs (per-student scores, question-level analysis) but not how data is stored

**Communication style:**
- Uses educator vocabulary naturally: "formative assessment," "differentiated instruction," "learning objectives," "exit ticket"
- Enthusiastic and specific about classroom needs
- Defers completely on technology: "whatever works best"
- Time-pressured: "I have 30 minutes of prep before first period"
- Will describe desired behavior through classroom scenarios, not features

**Current motivation:** Kahoot is fun but doesn't give per-student question-level data. Google Forms is free but clunky and not real-time. She wants something simple enough that her students can join with a code on any device in under 30 seconds, take a quiz, and she can see who's struggling with which concepts in real-time.

## Evaluation Procedure

### Setup

1. Create an isolated project directory for the evaluation:
   ```bash
   python3 tools/prawduct-setup.py setup /tmp/eval-quiz-platform --name "QuickCheck"
   ```

### Running the evaluation

3. Start a new LLM conversation in `/tmp/eval-quiz-platform`. The generated repo is self-contained (own CLAUDE.md, hooks, Critic instructions).
4. Send the Input prompt (below) as the user's opening message.
5. For each system question, respond using the scripted Test Conversation responses below. If the system asks about a topic not covered, respond in character as Priya Chandran (see Test Persona).
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
    rm -rf /tmp/eval-quiz-platform
    ```

## Input

> "I want to build a quiz app for my classroom. I teach 8th grade science and I need something where I can create quizzes, my students join with a code on their phones or Chromebooks, and I can see their answers in real-time so I know who's getting it and who needs help."

The input signals:
- Multiple party types ("I create" vs. "students join" — creator and consumer)
- Human interface (app, phones, Chromebooks)
- Education domain (8th grade, classroom, formative assessment)
- Real-time feedback need
- Non-technical user (teacher describing behavior, not technology)
- Specific device constraints (phones and Chromebooks)

## Test Conversation

To ensure repeatable evaluation, the following scripted responses define what Priya Chandran says when asked about each topic. The evaluator provides these responses regardless of how the system phrases its questions. If the system doesn't ask about a topic (e.g., because it infers the answer), the corresponding response is not volunteered.

**When asked to confirm classification or assumptions:**
> "Yes, that sounds right."
>
> Accept reasonable inferences. Only correct if the system misunderstands the classroom context.

**When asked about users / who uses it:**
> "Me — I create the quizzes and see the results. And my students — they take the quizzes during class. I have about 120 students across 4 class periods."

**When asked about student ages:**
> "They're 13 and 14, 8th graders."

**When asked about how students join / access:**
> "I want to project a code on the board, they type it into their phone or Chromebook browser, and they're in. No accounts, no passwords — just a code and their name. It needs to be fast, like under 30 seconds to get started."

**When asked about what kinds of questions:**
> "Mostly multiple choice for now. Maybe short answer later. I just need to see quickly who picked what."

**When asked about what the teacher sees during a quiz:**
> "I want a live view — like a dashboard where I can see how many students have answered, what percentage got each question right, and maybe which specific students are struggling. I use it to decide whether to re-teach a concept."

**When asked about grading / scoring:**
> "Auto-graded for multiple choice. I don't need letter grades — just a score and which questions each student got wrong. I use it for formative assessment, not final grades."

**When asked about data / what results to keep:**
> "I'd want to keep quiz results for the semester so I can look back at trends. Like, did my students improve on the force and motion unit after I re-taught it?"

**When asked about privacy / student data concerns:**
> "Oh, good point. I don't want to collect anything beyond their name and answers. No email, no location. The school is strict about student privacy — we had a whole training on it."

**When asked about whether other teachers would use it:**
> "Maybe eventually? For now just me. But if it works well I'd share it with my department — there are 5 of us."

**When asked about platform / device specifics:**
> "It needs to work in a web browser — no app installs. Our Chromebooks can't install apps, and I can't ask parents to install things on their kids' phones."

**When asked about existing tools / why not use Kahoot, etc.:**
> "Kahoot is fun but it's more of a game — I can't see per-student question-level data after. Google Forms works but it's not real-time and it's clunky to set up. I want something in between."

**When asked about anything not covered above:**
> Give a brief answer in educator language, consistent with the persona: an experienced, enthusiastic teacher who knows exactly what she wants pedagogically but defers completely on technology choices.

**General persona:** Enthusiastic, pedagogically specific, non-technical, time-conscious. Describes behavior through classroom scenarios. Defers on all technical decisions.

## Evaluation Rubric

### Discovery (C2)

**Must-do:**

- `[simulation]` Detect `has_multiple_party_types`: teachers (create quizzes, view analytics) and students (take quizzes, see own scores).
- `[simulation]` Detect `has_human_interface` (web application, multiple device types).
- `[simulation]` Probe for or infer student ages and surface data sensitivity considerations (students are 13-14, borderline COPPA).
- `[simulation]` Classify domain as education.
- `[simulation]` Assign medium risk (multiple party types, student data, school privacy expectations).
- `[interactive]` Ask about both party types' core workflows (teacher flow vs. student flow).
- `[interactive]` Surface the join mechanism (code-based access, no accounts).
- `[interactive]` Surface data retention needs (semester history for trend analysis).
- `[interactive]` Surface student privacy as a consideration, proportionately.
- `[interactive]` Surface platform constraints (browser-only, Chromebooks, no installs).
- `[simulation]` Limit total discovery questions to 8-12 for this risk level.

**Must-not-do:**

- `[interactive]` Must not ask about enterprise SSO, LDAP, or Active Directory integration.
- `[interactive]` Must not ask about monetization, subscription tiers, or pricing.
- `[interactive]` Must not ask about LMS integration (Canvas, Blackboard) — the user didn't mention it.
- `[interactive]` Must not recommend using Kahoot or Google Forms instead.
- `[interactive]` Must not present technical alternatives for the user to choose between (React vs. Vue, SQL vs. NoSQL).
- `[interactive]` Must not use unexplained technical jargon with this non-technical user.
- `[simulation]` Must not generate more than 15 discovery questions total.

**Quality criteria:**

- `[interactive]` Questions use educator-accessible language: "What do students see after they finish?" not "What's the post-submission UX flow?"
- `[interactive]` The system recognizes the two distinct experiences from the input without needing to be told "there are two user types."
- `[interactive]` The system brings expertise about classroom constraints (device diversity, network reliability, join speed) without interrogating.
- `[interactive]` Student privacy is raised as a genuine concern (school training, student ages) but not as an enterprise compliance checklist.
- `[interactive]` Prior art awareness is proportionate: acknowledges Kahoot/Google Forms limitations that the user raised; doesn't lecture about the EdTech landscape.

### Session Management (C1)

**Must-do:**

- `[interactive]` Progress through discovery → planning without excessive back-and-forth.
- `[interactive]` Detect non-technical user from input style and vocabulary.
- `[interactive]` Adjust vocabulary accordingly — no unexplained jargon.
- `[interactive]` Make reasonable assumptions and state them explicitly.
- `[interactive]` Recognize when discovery is sufficient and transition to planning.

**Must-not-do:**

- `[interactive]` Must not conduct more than 3 rounds of discovery questions for this risk level.
- `[interactive]` Must not use technical terminology without plain-language explanation.
- `[interactive]` Must not ask the user to choose between technical alternatives.
- `[interactive]` Must not require the user to make decisions outside their expertise.

**Quality criteria:**

- `[interactive]` Discovery completes in 2-3 question rounds.
- `[interactive]` The user doesn't feel interrogated or out of their depth.
- `[interactive]` Assumptions are stated clearly enough that the user can correct them.
- `[interactive]` Transitions between topics happen naturally, not abruptly.

### Planning (C3)

**Must-do (universal artifacts):**

- `[simulation]` Produce universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, observability strategy, dependency manifest.
- `[simulation]` All artifacts have correct YAML frontmatter with dependency declarations.

**Must-do (human-interface artifacts):**

- `[simulation]` Produce human-interface artifacts proportionate to a medium-risk classroom tool: interaction design or screen specs, information architecture, accessibility spec, onboarding spec.
- `[simulation]` Human-interface artifacts reflect TWO distinct experiences: teacher screens (quiz creation, live dashboard, results history) and student screens (join, take quiz, see score).
- `[simulation]` Screen inventory covers: teacher quiz creation, teacher live dashboard, teacher results/history view, student join screen, student quiz-taking screen, student results screen.

**Must-do (multi-party artifacts):**

- `[simulation]` Produce per-party experience specifications: teacher experience (create, monitor, analyze) and student experience (join, take, review).
- `[simulation]` Produce trust boundary analysis: teachers see all student data for their classes; students see only their own scores; students cannot see each other's results; join codes scope access to a specific quiz session.
- `[simulation]` Produce data isolation rules: per-class data separation, per-student score visibility, teacher-only analytics access.

**Must-do (content quality):**

- `[simulation]` Data model includes at minimum: Teacher, Student (or Participant), Quiz, Question, Answer/Response, QuizSession (with join code), Result entities.
- `[simulation]` Security model addresses: join-code access (no accounts for students), teacher authentication, student data visibility restrictions, session expiration.
- `[simulation]` Test specifications include per-party scenarios: teacher creates quiz, student joins with code, real-time results update, student sees only own score.
- `[simulation]` Test specifications include trust boundary tests: student cannot access another student's results, student cannot access teacher dashboard, expired join code is rejected.

**Must-not-do:**

- `[simulation]` Must not generate API-specific artifacts (no public API is described).
- `[simulation]` Must not generate automation/pipeline artifacts.
- `[simulation]` Must not over-engineer for scale (120 students, not 120,000).
- `[simulation]` Must not specify enterprise authentication for students (no accounts, just join codes).
- `[simulation]` Must not include LMS integration, gamification, or analytics beyond what the teacher described.

**Quality criteria:**

- `[simulation]` Per-party specs are genuinely distinct — the teacher spec is not just the student spec with "plus admin features."
- `[simulation]` Trust boundary analysis is specific and testable, not generic "role-based access."
- `[simulation]` Artifacts are internally consistent: entities in the data model appear in test specs and per-party flows.
- `[simulation]` A developer reading these artifacts understands both the teacher experience and the student experience well enough to build them as distinct flows.
- `[simulation]` Proportionality: artifacts total 8-15 pages across universal + human-interface + multi-party artifacts. No single artifact exceeds 4 pages.

### Review Perspectives (C4)

**Must-do:**

- `[simulation]` Product perspective: confirms this solves a real problem (formative assessment gap between Kahoot and Google Forms); scope is appropriate for a single-teacher tool.
- `[simulation]` Design perspective: raises the student join experience (must be fast — under 30 seconds), device diversity (phone vs. Chromebook screen sizes), and the teacher's live dashboard information density.
- `[simulation]` Architecture perspective: raises real-time update mechanism (WebSocket, SSE, or polling) and its implications for the teacher dashboard.
- `[simulation]` Skeptic perspective: raises at least one realistic concern (e.g., what happens when a student loses connection mid-quiz, classroom WiFi reliability, what if two teachers create quizzes with the same code).
- `[simulation]` At least one perspective raises student data privacy and age considerations.
- `[simulation]` Each finding has a specific recommendation and severity level.

**Must-not-do:**

- `[simulation]` Must not raise enterprise-scale concerns (high availability, multi-region, horizontal scaling).
- `[simulation]` Must not produce vague findings ("consider the student experience").
- `[simulation]` Must not block on concerns disproportionate to a classroom tool.

**Quality criteria:**

- `[simulation]` Findings are specific and actionable.
- `[simulation]` Severity ratings are proportionate to the product's risk level.
- `[simulation]` Multi-party concerns are addressed specifically (not just "add permissions").
- `[simulation]` No single perspective produces more than 4-6 findings for a medium-risk tool.

### Project State (C5)

**Must-do (structural):**

- `[simulation]` All populated fields use correct types per the template schema.
- `[simulation]` No fields added that don't exist in the template schema.
- `[simulation]` Risk factors include rationale.

**Must-do (content after discovery → planning):**

- `[simulation]` `classification.structural.has_multiple_party_types`: not null, listing teachers and students as distinct party types.
- `[simulation]` `classification.structural.has_human_interface`: not null, with modality "screen" and platform indicating web.
- `[simulation]` `classification.domain`: populated ("education" or "EdTech").
- `[simulation]` `classification.risk_profile.overall`: "medium".
- `[simulation]` `classification.risk_profile.factors`: at least 3 factors with rationale (multi-party trust, student data sensitivity, device diversity).
- `[simulation]` `product_definition.vision`: specific one-sentence description mentioning classroom quizzes and real-time teacher feedback.
- `[simulation]` `product_definition.users.personas`: at least 2 personas — one teacher, one student — with distinct needs.
- `[simulation]` `product_definition.core_flows`: at least 3 flows (teacher creates quiz, student takes quiz, teacher views live results).
- `[simulation]` `product_definition.scope.v1`: includes quiz creation, join-code access, real-time results, multiple choice.
- `[simulation]` `product_definition.scope.later`: at least 2 deferred items (e.g., short answer questions, multiple teacher support, LMS integration).
- `[simulation]` `product_definition.platform`: populated (web, browser-based).
- `[simulation]` `technical_decisions`: at least one decision about real-time mechanism and one about data storage, each with rationale.
- `[simulation]` `design_decisions.accessibility_approach`: populated, mentioning device diversity (Chromebooks, phones).
- `[simulation]` `user_expertise`: `technical_depth` at beginner or novice level.

**Must-not-do:**

- `[simulation]` Must not leave `has_multiple_party_types` null or empty after discovery.
- `[simulation]` Must not set risk below "medium" given multi-party and student data concerns.
- `[simulation]` Must not add `runs_unattended` or `multi_process_or_distributed` for this product.

**Quality criteria:**

- `[simulation]` A reader of `project-state.yaml` alone can understand: this is a web-based classroom quiz tool with two user types (teachers and students), used for real-time formative assessment.
- `[simulation]` Both party types are clearly represented in personas, flows, and scope.
- `[simulation]` Values are specific, not generic ("8th-grade science teacher creating real-time formative assessment quizzes" not "an education application").

## End-to-End Success Criteria

The scenario succeeds when:

1. Starting from the input above, the system correctly detects `has_multiple_party_types` (teachers and students) and `has_human_interface` (web).
2. Discovery surfaces per-party workflow differences, trust boundaries, and data isolation requirements without the user explicitly requesting them.
3. The system probes for or infers student age-related data sensitivity and raises it proportionately.
4. Universal artifacts are generated with correct frontmatter, proportionate to a medium-risk classroom tool.
5. Multi-party artifacts are generated: per-party experience specs, trust boundary analysis, data isolation rules.
6. Human-interface artifacts reflect two distinct experiences (teacher screens vs. student screens), not one experience with permission toggles.
7. Test specifications include trust boundary tests (student can't see other students' scores, etc.).
8. Vocabulary throughout is calibrated for a non-technical educator — no unexplained jargon.
9. The total output is proportionate — a reader should not think "this is enterprise EdTech for 120 students."
10. A developer reading the artifacts could build both the teacher experience and student experience without ambiguity on who sees what, who can do what, and how the trust model works.
