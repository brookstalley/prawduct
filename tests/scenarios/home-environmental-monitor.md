# Test Scenario: Home Environmental Monitor

## Scenario Overview

- **Primary structural:** `multi_process_or_distributed` (sensor collector + storage + web dashboard + alert evaluator)
- **Secondary structural:** `runs_unattended` (collector daemon), `has_human_interface` (web dashboard), `exposes_programmatic_interface` (sensor data API)
- **Domain:** IoT / Home automation (hobby)
- **Risk Level:** Low-Medium
- **Purpose:** Tests `multi_process_or_distributed` detection, system architecture artifact generation, process topology design, and IPC patterns. Tests the framework's ability to handle 4 overlapping structural characteristics for a realistic product. Tests Go build patterns and inverse vocabulary calibration (deeply technical user who is unfamiliar with one specific domain — web development).

## Why This Scenario Is Challenging

This scenario creates productive tension across multiple framework dimensions:

1. **Multi-process as the core architectural concern.** This product has 4 cooperating processes: a sensor collector (daemon), a storage service, a web dashboard, and an alert evaluator. The framework must produce a system architecture document covering process topology, IPC mechanisms, lifecycle management, and failure modes. This is fundamentally different from a single-process web app.

2. **Four overlapping structural characteristics.** Real products don't have one characteristic — they have several. The collector runs unattended, the dashboard has a human interface, the sensor data API is a programmatic interface, and the whole system is multi-process. The framework must generate artifacts for all four without producing contradictory or bloated specifications.

3. **Local multi-process, not cloud distributed.** "Multi-process" here means processes on one Raspberry Pi, not microservices across cloud regions. The framework must not conflate local IPC (Unix sockets, shared SQLite, HTTP on localhost) with distributed systems patterns (message brokers, service mesh, consensus protocols). Over-engineering this into a microservices architecture is a structural error.

4. **Hardware-adjacent domain.** Sensors exist in the physical world. The framework should surface hardware constraints (polling intervals, sensor reliability, network failures, power loss) without having hardcoded IoT knowledge. These are discovered through domain reasoning, not a questionnaire.

5. **Inverse vocabulary calibration.** The user has 35 years of engineering experience. She knows more about sensors, signal processing, and system reliability than the framework ever will. But she's never built a web dashboard. The framework must NOT over-explain systems concepts but SHOULD explain web concepts. This is the opposite of most scenarios where the user needs technical concepts explained.

6. **Process failure as a first-class concern.** What happens when the collector crashes? How does the dashboard know readings are stale? How does the alert evaluator handle a restart (does it re-evaluate all recent readings or miss the gap)? These are the questions that distinguish a toy prototype from a reliable system. The framework should surface them.

7. **Go idioms.** Go has specific patterns: goroutines for concurrency, channels for communication, `context.Context` for cancellation, `go test ./...` for testing, `go build` for compilation. The build cycle should reflect these, not impose JavaScript or Python patterns.

8. **Proportionality for a hobby project.** This is a retired engineer solving a home heating problem, not building industrial SCADA. But reliability matters — stale readings waste the HVAC contractor's time. The framework must be proportionate: serious about process reliability, not serious about five-nines uptime.

## Test Persona

**Name:** Margaret "Maggie" Kowalski

**Background:** 67 years old, retired electrical engineer with 35 years at an industrial controls company. Deep expertise in sensors, signal processing, embedded systems, serial protocols, and control systems. Has built dozens of Go CLI tools and utilities for personal projects since retiring. Comfortable with Linux, networking, and systems administration. Has never built a web application — her tools have always been terminal-based or headless. Lives in a 1920s house with wildly uneven heating (some rooms 10°F warmer than others) and wants data to prove it to the HVAC contractor.

**Technical expertise:**
- Expert: sensors, signal processing, embedded systems, serial protocols, Go, Linux systems administration, networking
- Comfortable: databases (PostgreSQL, SQLite), testing, CI/CD, process management (systemd)
- Novice: web development (HTML/CSS/JavaScript), frontend frameworks, WebSocket, browser APIs
- Unknown: modern web tooling (npm, webpack, Vite), CSS frameworks, responsive design

**Communication style:**
- Precise and methodical — specifies exact units, intervals, and thresholds
- Uses engineering terminology naturally ("polling interval", "sample rate", "hysteresis")
- Mildly impatient with imprecision or hand-waving ("what do you mean 'reasonable interval'?")
- Defers on web/frontend decisions with mild skepticism: "I don't need it to be pretty, I need it to be correct"
- Enjoys the engineering challenge — this is a fun retirement project, not a chore

**Current motivation:** She's been arguing with her HVAC contractor for months that the heating is uneven. He says "all old houses are like that." She wants hard data — 7 days of continuous temperature readings from 8 rooms — to bring to the next appointment and prove her case. If the system works well, she'll keep running it permanently.

## Evaluation Procedure

### Setup

1. Create an isolated project directory for the evaluation:
   ```bash
   python3 tools/prawduct-setup.py setup /tmp/eval-home-monitor --name "ThermoGraph"
   ```

### Running the evaluation

3. Start a new LLM conversation in `/tmp/eval-home-monitor`. The generated repo is self-contained (own CLAUDE.md, hooks, Critic instructions).
4. Send the Input prompt (below) as the user's opening message.
5. For each system question, respond using the scripted Test Conversation responses below. If the system asks about a topic not covered, respond in character as Maggie Kowalski (see Test Persona).
6. Let the system run through discovery → planning → building → iteration.

### Evaluating results

7. After the run completes, evaluate against the Evaluation Rubric (below) by checking:
   - `.prawduct/project-state.yaml` against the C5 criteria
   - `.prawduct/artifacts/*.md` against the C3 criteria
   - The conversation transcript against C1, C2, and C4 criteria
   - The running application against the Build and Iteration criteria
8. Record pass/fail for each must-do, must-not-do, and quality criterion.

### Recording results

9. **Before cleanup**, record evaluation results. Include: scenario name, date, framework version (git SHA), pass/fail per rubric criterion with evidence, and issues found.

### Cleanup

10. Delete the evaluation directory when done:
    ```bash
    rm -rf /tmp/eval-home-monitor
    ```

## Input

> "I want to build a home environmental monitoring system in Go. I have 8 temperature and humidity sensors around my house connected to my local network — they're ESP32s with HTTP endpoints that return JSON readings. I need a collector that polls them every 5 minutes, stores the data in SQLite, a simple web dashboard to view current readings and 7-day charts, and alerts when temperature drops below 60°F or goes above 80°F. Everything runs on a Raspberry Pi in my basement."

The input signals:
- Multi-process system (collector + storage + dashboard + alerts — distinct processes)
- Runs unattended (collector daemon, always polling)
- Has human interface (web dashboard)
- Exposes programmatic interface (sensors have HTTP endpoints; the system may expose an API)
- Technical user (Go, ESP32, HTTP, JSON, SQLite, Raspberry Pi)
- Specific domain (IoT/environmental monitoring)
- Hardware-adjacent (physical sensors, local network)
- Exact specifications (8 sensors, 5-minute interval, 60°F/80°F thresholds, 7 days)

## Test Conversation

To ensure repeatable evaluation, the following scripted responses define what Maggie Kowalski says when asked about each topic. The evaluator provides these responses regardless of how the system phrases its questions. If the system doesn't ask about a topic (e.g., because it infers the answer), the corresponding response is not volunteered.

**When asked to confirm classification or assumptions:**
> "That's correct."
>
> Accept reasonable inferences. Correct if the system makes a wrong assumption about the sensors or system architecture.

**When asked about sensor details / HTTP endpoint format:**
> "Each ESP32 runs a tiny HTTP server. GET /reading returns JSON: `{\"temperature_f\": 72.3, \"humidity_pct\": 45.1, \"sensor_id\": \"living-room\"}`. They're on static IPs on my LAN. Reliable when powered, but they occasionally drop off the network for a few seconds during WiFi congestion."

**When asked about the collector architecture / how it should work:**
> "A single Go process that polls all 8 sensors sequentially every 5 minutes. If a sensor doesn't respond within 5 seconds, log the failure and move on — don't block the other sensors. Store each reading with a timestamp in SQLite."

**When asked about the dashboard / what to display:**
> "Current readings for all 8 sensors in a table. A chart showing temperature over the last 7 days for each sensor — one line per sensor. Humidity would be nice too but temperature is the priority. I don't need it to be pretty, I need it to be correct."

**When asked about alerts / notification mechanism:**
> "For now, just write alerts to a log file and display them on the dashboard. If temperature goes below 60°F or above 80°F for more than 2 consecutive readings — not just a single spike. I don't need email or SMS alerts for v1."

**When asked about how the processes relate / system architecture:**
> "I'm thinking: the collector runs as a systemd service, always polling. It writes to SQLite. The web dashboard reads from the same SQLite database. The alert evaluator can be part of the collector or a separate process — I'm open to either. They all run on the same Raspberry Pi."

**When asked about the web technology / frontend:**
> "I have no opinion on frontend frameworks — I've never built a web UI. Whatever's simplest to serve from a Go backend. Even server-rendered HTML templates would be fine. I just need a page I can open in a browser."

**When asked about data retention / how long to keep readings:**
> "Keep everything for at least a year. At 8 sensors × 1 reading per 5 minutes, that's about 840,000 rows per year. SQLite handles that fine."

**When asked about who accesses the system:**
> "Just me, on my home network. No remote access, no authentication needed. If I want to check from outside the house, I'll VPN in."

**When asked about failure handling / what happens when things go wrong:**
> "The collector should be resilient — if SQLite is locked or a sensor is down, log and retry next cycle. The dashboard should show stale data with a clear timestamp so I know when the last reading was. If the Pi reboots, systemd restarts the collector automatically."

**When asked about testing / how to verify the system works:**
> "I can write a mock HTTP server that simulates sensor responses for testing. The important thing is: the collector handles timeouts and failures gracefully, the data gets stored correctly, the charts render actual data, and the alerts fire at the right thresholds."

**When asked about anything not covered above:**
> Give a precise, technical answer consistent with the persona: a retired electrical engineer who is deeply expert in sensors and systems but unfamiliar with web development. Uses engineering units and exact specifications. Mildly impatient with vagueness.

**General persona:** Precise, methodical, deeply technical in systems/hardware, novice in web development. Values correctness over aesthetics. Gives exact specifications when asked.

## Test Conversation (Build)

These scripted responses extend the test conversation for the build stages.

**When asked to confirm the build plan:**
> "Looks good. Let's build it."

**When shown progress during building (chunk completion messages):**
> [No response needed. Accept silently unless the system explicitly asks a question.]

**When the system surfaces an implementation issue:**
> "What do you recommend?"
>
> Accept the system's recommendation. Maggie trusts engineering judgment on software architecture. She would only push back on sensor-related decisions.

**When presented with the working system and asked to try it:**
> "Can you add CSV export? I need to bring the last 7 days of temperature readings to the HVAC appointment next Thursday."

**When asked about additional changes after the CSV export:**
> "That's everything I need for now. Thank you."

**General persona (continued):** Same as discovery — precise, methodical, values correctness. During build, she's hands-off on software decisions but engaged on sensor/data correctness.

## Evaluation Rubric

### Discovery (C2)

**Must-do:**

- `[simulation]` Detect `multi_process_or_distributed` structural characteristic (collector + storage + dashboard + alerts as cooperating processes).
- `[simulation]` Detect `runs_unattended` (collector daemon).
- `[simulation]` Detect `has_human_interface` (web dashboard).
- `[simulation]` Detect `exposes_programmatic_interface` (sensor HTTP endpoints; and potentially the system's own data API).
- `[simulation]` Classify domain as IoT, home automation, or environmental monitoring.
- `[simulation]` Assign low-medium risk (hobby project, but reliability matters for the data collection goal).
- `[interactive]` Ask about or confirm process architecture (which processes, how they communicate).
- `[interactive]` Surface failure modes: sensor timeout, database lock, stale readings, process crash recovery.
- `[interactive]` Surface data retention and storage sizing.
- `[interactive]` Ask about the dashboard technology preference (since user is a web novice).
- `[interactive]` Surface alert threshold hysteresis (the user wants 2 consecutive readings, not single-spike alerts).
- `[simulation]` Limit total discovery questions to 8-12 for this risk level.

**Must-not-do:**

- `[interactive]` Must not over-explain systems concepts (polling, timeouts, systemd, SQLite) to a 35-year veteran engineer.
- `[interactive]` Must not suggest cloud services, message brokers, or microservices architecture for a local Raspberry Pi system.
- `[interactive]` Must not recommend container orchestration (Docker Compose, k8s) for a single-machine hobby project.
- `[interactive]` Must not ask about enterprise monitoring (Grafana, Prometheus, Datadog) unless as lightweight options.
- `[interactive]` Must not ask about authentication for a local-only system.
- `[interactive]` Must not ask about scaling, load balancing, or high availability.
- `[simulation]` Must not generate more than 15 discovery questions total.

**Quality criteria:**

- `[interactive]` The system correctly identifies the multi-process nature as the primary architectural concern.
- `[interactive]` Web/frontend concepts are explained when raised (since the user is a web novice), while systems concepts are used at expert level.
- `[interactive]` Failure handling questions demonstrate understanding of long-running daemon concerns (crash recovery, stale data detection, graceful degradation).
- `[interactive]` Prior art awareness is proportionate: may briefly mention existing home monitoring solutions; respects the user's choice to build.
- `[interactive]` The system brings web architecture expertise the user lacks: explains that "a simple web dashboard" involves HTTP routing, HTML templating, and possibly JavaScript for charts — without being condescending.

### Session Management (C1)

**Must-do:**

- `[interactive]` Progress through discovery → planning without excessive back-and-forth.
- `[interactive]` Detect expert-level technical user from input vocabulary and calibrate accordingly.
- `[interactive]` Use systems engineering vocabulary at the user's level.
- `[interactive]` Explain web concepts without condescension when they arise.
- `[interactive]` Make reasonable assumptions and state them explicitly.
- `[interactive]` Recognize when discovery is sufficient and transition to planning.

**Must-not-do:**

- `[interactive]` Must not over-explain Go, Linux, networking, databases, or sensor concepts.
- `[interactive]` Must not conduct more than 2-3 rounds of discovery for this risk level.
- `[interactive]` Must not present the user with web framework comparisons she can't evaluate.

**Quality criteria:**

- `[interactive]` Discovery completes in 2-3 question rounds.
- `[interactive]` The conversation respects the user's deep expertise in her domain while supplementing her web knowledge gap.
- `[interactive]` Technical decisions on web architecture are made by the system (with explanation) rather than delegated to the user.

### Planning (C3)

**Must-do (universal artifacts):**

- `[simulation]` Produce universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, observability strategy, dependency manifest.
- `[simulation]` All artifacts have correct YAML frontmatter with dependency declarations.

**Must-do (multi-process artifact — primary):**

- `[simulation]` Produce system architecture document covering:
  - Process topology: which processes exist, their responsibilities, and their lifecycle (long-running daemon vs. on-demand)
  - Communication channels: how processes communicate (shared SQLite, HTTP on localhost, filesystem)
  - Concurrency model: how the collector handles 8 sensors (sequential with timeouts, as user specified)
  - Persistence boundaries: what's durable (SQLite readings) vs. ephemeral (in-memory alert state, dashboard render cache)
- `[simulation]` System architecture clearly states these are LOCAL processes on one machine, not distributed services.

**Must-do (secondary structural artifacts):**

- `[simulation]` Unattended/automation artifacts: scheduling (systemd unit), monitoring approach (process health, stale reading detection), failure recovery (auto-restart, graceful degradation).
- `[simulation]` Human-interface artifacts: dashboard screen spec (current readings table, 7-day chart, alert display). Proportionate — one page, not a full interaction design.
- `[simulation]` API artifact (if the system exposes its own data API): endpoint specs for reading data. Or explicit note that sensors have their own API and the system is a consumer, not a provider.

**Must-do (content quality):**

- `[simulation]` Data model includes at minimum: Sensor (id, name/location, type), Reading (sensor_id, timestamp, temperature, humidity), Alert (sensor_id, threshold, triggered_at, resolved_at), AlertRule (threshold, consecutive_count).
- `[simulation]` Test specifications include multi-process scenarios: collector handles sensor timeout, dashboard shows stale reading indicator, alert evaluator respects consecutive-reading threshold.
- `[simulation]` Test specifications include a mock sensor approach for repeatable testing.
- `[simulation]` Operational spec addresses: systemd service configuration, SQLite on Raspberry Pi (file path, WAL mode for concurrent access), log file location.
- `[simulation]` Dependency manifest reflects Go ecosystem: standard library where possible, specific charting library for dashboard, SQLite driver.

**Must-not-do:**

- `[simulation]` Must not specify cloud infrastructure, message brokers, or container orchestration.
- `[simulation]` Must not over-engineer: no service mesh, no API gateway, no distributed tracing for a single-machine system.
- `[simulation]` Must not under-engineer: process lifecycle and failure handling are real concerns that deserve specification.
- `[simulation]` Must not conflate "multi-process on one machine" with "distributed microservices."

**Quality criteria:**

- `[simulation]` System architecture document is the standout artifact — a reader understands exactly which processes run, how they communicate, and what happens when one fails.
- `[simulation]` Artifacts reflect Go idioms where relevant (goroutines, channels, standard library HTTP server).
- `[simulation]` Artifacts are internally consistent across all 4 structural characteristics.
- `[simulation]` A Go developer reading these artifacts could build the system without ambiguity on process boundaries, IPC mechanisms, or failure handling.
- `[simulation]` Proportionality: thorough on architecture and reliability, light on aesthetics and enterprise concerns.

### Review Perspectives (C4)

**Must-do:**

- `[simulation]` Product perspective: confirms this solves a real problem (proving uneven heating with data); scope is appropriate for a hobby project with a concrete goal.
- `[simulation]` Architecture perspective: raises process lifecycle management (what happens on crash/restart), SQLite concurrent access patterns (WAL mode, reader/writer contention), and stale reading detection.
- `[simulation]` Skeptic perspective: raises at least one concern about long-running reliability (e.g., SQLite file growth, sensor ID changes after power loss, clock drift on Raspberry Pi, what happens during a power outage).
- `[simulation]` Testing perspective: raises the need for mock sensors and integration tests that verify the full collector → storage → dashboard pipeline.
- `[simulation]` Each finding has a specific recommendation and severity level.

**Must-not-do:**

- `[simulation]` Must not raise cloud deployment or scaling concerns for a Raspberry Pi system.
- `[simulation]` Must not produce vague findings.
- `[simulation]` Must not block on concerns disproportionate to a hobby project.

**Quality criteria:**

- `[simulation]` Findings are specific and actionable.
- `[simulation]` Multi-process concerns are prominent (process lifecycle, IPC correctness, concurrent database access).
- `[simulation]` Severity ratings are proportionate (data correctness is WARNING/BLOCKING; aesthetic issues are NOTE).
- `[simulation]` No single perspective produces more than 4-5 findings.

### Project State (C5)

**Must-do (structural):**

- `[simulation]` All populated fields use correct types per the template schema.
- `[simulation]` No fields added that don't exist in the template schema.
- `[simulation]` Risk factors include rationale.

**Must-do (content after discovery → planning):**

- `[simulation]` `classification.structural.multi_process_or_distributed`: not null, describing the process topology.
- `[simulation]` `classification.structural.runs_unattended`: not null (collector daemon).
- `[simulation]` `classification.structural.has_human_interface`: not null (web dashboard).
- `[simulation]` `classification.structural.exposes_programmatic_interface`: not null or explicitly noted as consumer-only (sensors expose APIs; the system consumes them).
- `[simulation]` `classification.domain`: populated ("IoT", "home automation", or "environmental monitoring").
- `[simulation]` `classification.risk_profile.overall`: "low-medium" or "medium".
- `[simulation]` `classification.risk_profile.factors`: at least 2 factors with rationale (data correctness for HVAC appointment, long-running reliability, hardware failure modes).
- `[simulation]` `product_definition.vision`: specific one-sentence description mentioning environmental monitoring and data collection.
- `[simulation]` `product_definition.scope.v1`: includes collector, storage, dashboard, threshold alerts, specific sensor count and polling interval.
- `[simulation]` `product_definition.scope.later`: at least 1 deferred item (e.g., email/SMS alerts, additional sensor types, remote access).
- `[simulation]` `product_definition.platform`: populated (Go, Raspberry Pi, Linux).
- `[simulation]` `technical_decisions`: includes storage choice (SQLite), IPC approach, web framework for dashboard, each with rationale.
- `[simulation]` `user_expertise`: `technical_depth` at expert or advanced level.

**Must-not-do:**

- `[simulation]` Must not set risk above "medium" for a home hobby project.
- `[simulation]` Must not add `handles_sensitive_data` (temperature readings are not sensitive).
- `[simulation]` Must not add `has_multiple_party_types` (single user).

**Quality criteria:**

- `[simulation]` A reader of `project-state.yaml` alone can understand: this is a multi-process Go system on a Raspberry Pi that collects temperature/humidity data from 8 sensors and displays it on a web dashboard.
- `[simulation]` All 4 active structural characteristics are represented.
- `[simulation]` Values are specific ("8 ESP32 sensors, 5-minute polling interval, SQLite storage, 7-day charts" not "environmental monitoring system").

### Build Plan

**Must-do:**

- `[simulation]` Generate a build plan with at least 5 chunks: scaffold + data layer, sensor collector, alert evaluator, web dashboard, integration/polish.
- `[simulation]` Every core flow from the Product Brief is mapped to at least one chunk.
- `[simulation]` Each chunk has acceptance criteria traceable to test specification scenarios.
- `[simulation]` First chunk proves the architecture: a sensor reading goes from collector → SQLite → read back. This validates the process boundary and IPC mechanism.
- `[simulation]` Scaffolding chunk specifies exact Go project initialization (`go mod init`, directory structure).
- `[simulation]` Web dashboard chunk explicitly addresses the user's web knowledge gap — framework choice is made for her, not delegated.
- `[simulation]` Governance checkpoints include at least one mid-build and one final review.

**Must-not-do:**

- `[simulation]` Must not produce more than 8 chunks for this project.
- `[simulation]` Must not require the user to make web framework decisions.
- `[simulation]` Must not include chunks for features not in v1 scope.

**Quality criteria:**

- `[simulation]` Chunk ordering makes architectural sense: data layer → collector → alerts → dashboard (data producers before consumers).
- `[simulation]` A Go developer reading this plan could execute it without making architectural decisions.
- `[simulation]` The plan is proportionate — not enterprise build infrastructure for a Raspberry Pi project.

### Builder

**Must-do:**

- `[simulation]` Scaffold chunk works: `go build ./...` compiles, `go test ./...` passes.
- `[simulation]` Collector polls mock sensors (or real ones if available) and stores readings in SQLite.
- `[simulation]` Dashboard serves HTTP, shows current readings and charts.
- `[simulation]` Alert evaluator triggers on consecutive threshold violations, not single spikes.
- `[simulation]` Tests are written alongside each chunk, not all at the end.
- `[simulation]` All tests pass after every chunk (`go test ./...` exits 0).
- `[simulation]` Mock sensor server is included for repeatable testing.

**Must-not-do:**

- `[simulation]` Must not choose technologies not specified in the build plan.
- `[simulation]` Must not add features not in chunk deliverables.
- `[simulation]` Must not delete or weaken tests from previous chunks.
- `[simulation]` Must not skip testing for any feature chunk.

**Quality criteria:**

- `[simulation]` Go code follows Go conventions (gofmt, package structure, error handling with explicit checks).
- `[simulation]` Process boundaries are clean: collector, dashboard, and alert evaluator could be separated into independent binaries if needed later.
- `[simulation]` The system actually works: collector stores readings, dashboard displays them, alerts trigger correctly.
- `[simulation]` Test names are specific and descriptive.

### Critic Product Governance

**Must-do:**

- `[simulation]` Critic review runs after each feature chunk.
- `[simulation]` Test count never decreases between chunks.
- `[simulation]` Critic actively reviews each feature chunk with at least 2 specific findings per feature chunk (any severity), each with file/line references.
- `[simulation]` Critic review was invoked automatically, not prompted by user request.
- `[simulation]` At least one finding addresses multi-process concerns (process lifecycle, IPC correctness, concurrent database access, stale data handling).
- `[simulation]` Fix-by-fudging detection is active: if a test is weakened to pass, the Critic catches it.

**Must-not-do:**

- `[simulation]` Must not produce more than 6 findings per chunk for this low-medium risk product.
- `[simulation]` Must not block on concerns disproportionate to the product's risk level.
- `[simulation]` Must not approve a chunk where multi-process concerns are unaddressed.

**Quality criteria:**

- `[simulation]` Findings are specific and actionable.
- `[simulation]` The review cycle converges: blocking findings → fix → re-review → clear.
- `[hybrid]` Process feels proportionate — the Critic helps maintain system reliability without obstructing a hobby project.

### Iteration

**Must-do:**

- `[simulation]` CSV export request ("bring the last 7 days of temperature readings to the HVAC appointment") is classified as **functional** (new data export feature).
- `[simulation]` Change impact assessment identifies affected artifacts: at minimum, test specifications, and possibly the API contract or operational spec.
- `[simulation]` Affected artifacts are updated before implementation.
- `[simulation]` New test(s) written for CSV export behavior (correct columns, correct date range, correct sensor filtering).
- `[simulation]` Existing tests still pass (no regressions).
- `[simulation]` The CSV export works: produces a valid CSV file with 7 days of temperature data.

**Must-not-do:**

- `[simulation]` Must not classify the CSV export as cosmetic (it adds a new data access mechanism).
- `[simulation]` Must not classify it as directional (it's a feature addition, not a product pivot).
- `[simulation]` Must not implement without updating test specifications.
- `[simulation]` Must not break existing collector, dashboard, or alert functionality.

**Quality criteria:**

- `[simulation]` The iteration cycle is efficient: one round of artifact update → build → review → done.
- `[hybrid]` The process doesn't feel heavyweight for a simple export feature.
- `[simulation]` CSV format is correct and useful: timestamps, sensor names, temperature values — ready to share with the HVAC contractor.

## End-to-End Success Criteria

The scenario succeeds when:

**Discovery → Planning:**

1. Starting from the input above, the system correctly detects all 4 structural characteristics: `multi_process_or_distributed` (primary), `runs_unattended`, `has_human_interface`, `exposes_programmatic_interface`.
2. Discovery surfaces multi-process architecture concerns (process topology, IPC, failure modes) as the primary design challenge.
3. System architecture artifact clearly describes local processes on one machine — not cloud microservices.
4. Artifacts cover all 4 structural characteristics without bloat or contradiction.
5. The total output is proportionate — a reader should not think "this is SCADA infrastructure for 8 temperature sensors."

**Building:**

6. Build plan translates the multi-process architecture into concrete, ordered chunks with Go-specific build commands.
7. All processes build and run: `go build ./...` compiles, `go test ./...` passes.
8. The full pipeline works: sensors polled → data stored → dashboard displays → alerts trigger.
9. Process failure is handled gracefully (sensor timeout, stale data detection).
10. The Critic reviews each chunk with findings that address multi-process concerns.

**Iteration:**

11. CSV export handled in one efficient iteration cycle.
12. Export produces correct, usable data for the HVAC appointment.
13. No regressions in existing functionality.
14. At least one learning captured during building (architecture discovery, multi-process testing challenge, or web framework for Go novice).
