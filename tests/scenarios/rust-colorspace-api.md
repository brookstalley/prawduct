# Test Scenario: Rust Colorspace Conversion API

## Scenario Overview

- **Primary structural:** `exposes_programmatic_interface` (REST API)
- **Domain:** Developer tools / Color science
- **Risk Level:** Medium
- **Purpose:** Tests `exposes_programmatic_interface` detection, API-specific artifact generation, and verification that the system does NOT generate human-interface artifacts for a pure API. Tests mathematical domain handling (color conversion formulas require precision testing) and Rust-specific build/test patterns.

## Why This Scenario Is Challenging

This scenario creates productive tension across multiple framework dimensions:

1. **API-only product.** The framework's artifact generation must correctly detect that this has NO human interface and suppress all UI artifacts. Generating screen specs for an API is a structural error.

2. **Mathematical correctness domain.** Color conversions have exact formulas with known reference values. Testing strategy must include property-based testing (round-trip fidelity), known test vectors, and edge cases (out-of-gamut colors, boundary values). This is fundamentally different from testing CRUD operations.

3. **N×N conversion matrix.** With 10 colorspaces, there are 90 possible directed conversions. The framework must surface API design decisions: implement all 90 directly, or use a hub-and-spoke model (convert through an intermediate space like CIE XYZ)? This is an architectural decision with significant implications for correctness, maintainability, and precision loss.

4. **Compiled language patterns.** Rust has different build/test idioms from JavaScript or Python: `cargo test`, `cargo run`, `cargo build --release`, strong type system, `Result` error handling, `serde` for serialization. The framework should adapt to these patterns without imposing scripting-language assumptions.

5. **API contract as primary artifact.** For an API product, the API contract is the most important structurally-triggered artifact — it defines the consumer experience. The framework must produce a contract specific enough to implement from: endpoint paths, HTTP methods, request/response schemas, error formats, status codes.

6. **Precision vs. practicality.** Some colorspace conversions are lossy (CMYK→sRGB depends on ICC profiles; perceptual spaces have gamut limitations). The framework should surface these nuances without making the project feel like a color science research paper.

7. **Degenerate artifacts.** Security model should be minimal (no auth for an internal tool). Operational spec should be simple (single binary). The framework should recognize these as proportionate, not lazy.

## Test Persona

**Name:** Kai Tanaka

**Background:** Senior backend engineer, 6 years of Rust experience at a B2B SaaS company. Has built several Rust microservices in production. Hobby photographer who knows color theory concepts (white balance, color profiles, gamut) but not the mathematics behind colorspace conversions. Building this as a weekend project that might also be useful for the design team at work.

**Technical expertise:**
- Deep Rust expertise (ownership, lifetimes, async, serde, axum/actix-web)
- Strong API design opinions (RESTful conventions, proper error responses, consistent schemas)
- Understands color concepts (RGB, HSL, CMYK) from photography but not the conversion math
- Comfortable with testing strategies (property-based testing with proptest, criterion for benchmarks)
- Has opinions about project structure, error handling patterns, and documentation

**Communication style:**
- Technical and precise — uses Rust terminology naturally
- Opinionated on API design ("I want proper error responses, not just 500s")
- Defers on color science ("I know what HSL is but not how to convert it to Lab")
- Pragmatic — wants a useful tool, not a perfect one
- Slightly impatient with non-technical questions ("It's a REST API, no users see it")

**Current motivation:** Design team keeps asking "what's the Lab equivalent of this hex color?" and Kai is tired of pointing them to random websites that may or may not be accurate. Wants a reliable, self-hosted tool with known correctness guarantees.

## Evaluation Procedure

### Setup

1. Create an isolated project directory for the evaluation:
   ```bash
   python3 tools/prawduct-setup.py setup /tmp/eval-colorspace-api --name "Chromavert"
   ```

### Running the evaluation

3. Start a new LLM conversation in `/tmp/eval-colorspace-api`. The generated repo is self-contained (own CLAUDE.md, hooks, Critic instructions).
4. Send the Input prompt (below) as the user's opening message.
5. For each system question, respond using the scripted Test Conversation responses below. If the system asks about a topic not covered, respond in character as Kai Tanaka (see Test Persona).
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
    rm -rf /tmp/eval-colorspace-api
    ```

## Input

> "I want to build a REST API in Rust that converts colors between colorspaces. All the common ones — RGB, HSL, HSV, CMYK, Lab, the works. JSON in, JSON out. Mostly for internal use by our design team, but I want it done right — accurate conversions with proper error handling."

The input signals:
- Programmatic interface (REST API, JSON)
- No human interface ("API", not "app" or "dashboard")
- Technical user (Rust, REST, JSON)
- Specific domain (colorspace conversion)
- Quality expectation (accuracy, proper error handling)
- Internal/low-scale usage

## Test Conversation

To ensure repeatable evaluation, the following scripted responses define what Kai Tanaka says when asked about each topic. The evaluator provides these responses regardless of how the system phrases its questions. If the system doesn't ask about a topic (e.g., because it infers the answer), the corresponding response is not volunteered.

**When asked to confirm classification or assumptions:**
> "Yeah, that's right."
>
> Accept reasonable inferences. Correct if the system makes a wrong assumption about Rust or API design.

**When asked about consumers / who uses the API:**
> "Mostly me hitting it from scripts, and maybe the design team through a simple curl wrapper or Postman. No public consumers."

**When asked about which colorspaces to support:**
> "The standard web and print ones for sure — sRGB, HSL, HSV, CMYK. The perceptual ones the designers care about — CIE Lab, Oklab, LCH, Oklch. Linear RGB and XYZ as the intermediate conversion spaces. So about 10 total."

**When asked about precision / accuracy requirements:**
> "It needs to be mathematically correct. If I convert sRGB to Lab and back, I should get the same values within floating-point tolerance. I want to trust this more than random websites."

**When asked about API design / endpoint structure:**
> "I'm thinking a single POST endpoint like `/convert` that takes the source colorspace, target colorspace, and the color values. Maybe a batch endpoint too for converting a whole palette. Standard REST, JSON request and response."

**When asked about error handling:**
> "Clear error responses with proper HTTP status codes. 400 for bad input — out-of-range values, unknown colorspace names, malformed JSON. 422 for valid input that can't be converted cleanly. I want the error body to say exactly what's wrong."

**When asked about batch operations / converting multiple colors:**
> "Yeah, that'd be useful. The design team has palettes of 10-20 colors they need converted all at once. Same endpoint or a `/batch` variant, either way."

**When asked about authentication / authorization:**
> "No auth needed. It's running on our internal network. If we ever expose it publicly we'd add API keys, but not for v1."

**When asked about deployment / infrastructure:**
> "Single binary, runs on my Mac for dev and a small Linux VM for the team. `cargo build`, copy the binary, done. No containers needed."

**When asked about performance requirements:**
> "It's a utility, not a video pipeline. Sub-100ms per single conversion is fine. I'd rather it be correct than fast."

**When asked about documentation / API docs:**
> "I'd love auto-generated API docs. Rust has good tools for that — utoipa or similar. But I'd settle for a well-documented README with curl examples for now."

**When asked about versioning:**
> "URL versioning, `/v1/convert`. Simple. We can add v2 if the schema ever changes."

**When asked about out-of-gamut / lossy conversions:**
> "Good question — some conversions are lossy. CMYK depends on ICC profiles, and gamut mapping isn't always reversible. I think we should document which conversions are lossless and which aren't, and maybe return a warning field in the response when precision is limited."

**When asked about anything not covered above:**
> Give a brief, technical, pragmatic answer consistent with the persona: a senior Rust developer who wants a well-built internal tool, not enterprise infrastructure.

**General persona:** Technical, opinionated about API design and Rust patterns, defers on color science math, pragmatic about scope.

## Evaluation Rubric

### Discovery (C2)

**Must-do:**

- `[simulation]` Detect `exposes_programmatic_interface` structural characteristic.
- `[simulation]` Confirm NO `has_human_interface` — this is a pure API with no user-facing screens.
- `[simulation]` Classify domain as developer tools or utility.
- `[simulation]` Assign medium risk (mathematical correctness matters, but limited consumers).
- `[interactive]` Ask about API consumers (who calls this, what are their usage patterns?).
- `[interactive]` Ask about colorspace coverage (which spaces, how many?).
- `[interactive]` Surface mathematical precision as a key concern.
- `[interactive]` Surface the API contract — endpoint structure, request/response format.
- `[interactive]` Surface error handling expectations for an API.
- `[interactive]` Surface lossy/lossless conversion nuances or the hub-and-spoke architecture question.
- `[simulation]` Limit total discovery questions to 6-10 for this risk level.

**Must-not-do:**

- `[interactive]` Must not ask about UI, screens, navigation, visual design, or user onboarding.
- `[interactive]` Must not ask about multiple user types or party types.
- `[interactive]` Must not ask about sensitive data, compliance, or regulatory concerns.
- `[interactive]` Must not recommend using an existing crate (e.g., `palette`) instead of building.
- `[interactive]` Must not ask about enterprise deployment (Kubernetes, load balancers, etc.).
- `[interactive]` Must not suggest adding a frontend or dashboard.
- `[simulation]` Must not generate more than 12 discovery questions total.

**Quality criteria:**

- `[interactive]` Questions demonstrate understanding of API design concerns (versioning, error contracts, batch operations, consumer documentation).
- `[interactive]` The system brings color science expertise: surfaces the hub-and-spoke conversion architecture, gamut limitations, or ICC profile dependency without the user raising them first.
- `[interactive]` Technical vocabulary matches the user's level — uses Rust terminology naturally (crates, serde, Result types, trait-based design).
- `[interactive]` Prior art awareness is proportionate: briefly acknowledges color conversion libraries exist; respects the user's choice to build an API.

### Session Management (C1)

**Must-do:**

- `[interactive]` Progress through discovery → planning without excessive back-and-forth.
- `[interactive]` Detect technical user from input vocabulary (Rust, REST, JSON) and calibrate accordingly.
- `[interactive]` Use technical terminology appropriate for a senior Rust developer.
- `[interactive]` Make reasonable assumptions and state them explicitly.
- `[interactive]` Recognize when discovery is sufficient and transition to artifact generation.

**Must-not-do:**

- `[interactive]` Must not over-explain basic concepts (REST, JSON, HTTP status codes) to a senior backend engineer.
- `[interactive]` Must not conduct more than 2-3 rounds of discovery for this risk level.
- `[interactive]` Must not ask the user to choose between options they've already indicated preference for (e.g., don't ask "REST or GraphQL?" when the user said "REST API").

**Quality criteria:**

- `[interactive]` Discovery completes in 2-3 question rounds.
- `[interactive]` The conversation feels like a peer technical discussion, not an interview.
- `[interactive]` The system recognizes Rust-specific constraints and opportunities without being told.

### Planning (C3)

**Must-do:**

- `[simulation]` Produce universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, observability strategy, dependency manifest.
- `[simulation]` Produce API-specific artifact: API contract with endpoint specifications, request/response schemas, error response format, HTTP status codes.
- `[simulation]` NOT produce human-interface artifacts (no screen specs, no information architecture, no design direction, no accessibility spec, no localization, no onboarding spec).
- `[simulation]` Data model includes: colorspace type definitions (with value ranges per space), conversion request/response types, batch request type, error types.
- `[simulation]` Test specifications include mathematical correctness tests with known reference values (e.g., sRGB(255, 0, 0) → HSL(0°, 100%, 50%)).
- `[simulation]` Test specifications include round-trip fidelity tests (convert A→B→A, verify within tolerance).
- `[simulation]` Test specifications include edge cases: boundary values (0, 255, 360°), out-of-gamut conversions, invalid input, empty batch.
- `[simulation]` API contract specifies at minimum: `/v1/convert` endpoint with POST method, request schema (source space, target space, color values), response schema (converted values plus metadata), error response schema with distinct codes.
- `[simulation]` Security model is minimal and explicitly proportionate (no auth for internal tool, with note about adding API keys if publicly exposed later).
- `[simulation]` Dependency manifest includes Rust-specific dependencies (web framework like axum or actix-web, serde, and either a color math crate or justification for hand-rolling conversions).

**Must-not-do:**

- `[simulation]` Must not generate any human-interface artifacts.
- `[simulation]` Must not specify enterprise deployment infrastructure.
- `[simulation]` Must not over-engineer the security model.
- `[simulation]` Must not specify a database for a stateless conversion API.

**Quality criteria:**

- `[simulation]` API contract is specific enough to implement from: a developer reading it knows exactly what to POST and what the response shape is.
- `[simulation]` Test specifications include at least 3 concrete reference value conversions with exact expected outputs.
- `[simulation]` Error handling spec distinguishes between input validation errors (400), semantically invalid conversions (422), and server errors (500).
- `[simulation]` Artifacts reflect Rust idioms where relevant (Result types for error handling, struct definitions for data model, trait-based conversion architecture).
- `[simulation]` Artifacts are internally consistent: colorspaces listed in the product brief match those in the data model, API contract, and test specifications.
- `[simulation]` A developer reading these artifacts could begin implementing in Rust without ambiguity on API shape, colorspace coverage, or error handling.

### Review Perspectives (C4)

**Must-do:**

- `[simulation]` Product perspective: confirms this solves a real problem (accurate, self-hosted color conversion); scope is appropriate for an internal tool.
- `[simulation]` Architecture perspective: raises the hub-and-spoke vs. direct conversion architecture decision and its implications for correctness and maintainability.
- `[simulation]` Skeptic perspective: raises at least one concern about mathematical accuracy (e.g., floating-point precision accumulation, CMYK profile dependency, gamut mapping limitations).
- `[simulation]` Testing perspective or Architecture perspective: raises the need for known reference values and round-trip property testing, not just unit tests of individual functions.
- `[simulation]` Each finding has a specific recommendation and severity level.

**Must-not-do:**

- `[simulation]` Must not raise UI/UX concerns for a headless API.
- `[simulation]` Must not raise enterprise scaling concerns for an internal tool.
- `[simulation]` Must not produce vague findings ("consider the error handling").

**Quality criteria:**

- `[simulation]` Findings are specific and actionable.
- `[simulation]` Severity ratings are proportionate to the product's risk level.
- `[simulation]` At least one finding addresses mathematical correctness — the core risk for this product.
- `[simulation]` No single perspective produces more than 3-5 findings for a medium-risk utility.

### Project State (C5)

**Must-do (structural):**

- `[simulation]` All populated fields use correct types per the template schema.
- `[simulation]` No fields added that don't exist in the template schema.
- `[simulation]` Risk factors include rationale.

**Must-do (content after discovery → planning):**

- `[simulation]` `classification.structural.exposes_programmatic_interface`: not null, with interface type "REST API".
- `[simulation]` `classification.structural.has_human_interface`: explicitly null or false.
- `[simulation]` `classification.domain`: populated ("developer tools" or "utility").
- `[simulation]` `classification.risk_profile.overall`: "medium".
- `[simulation]` `classification.risk_profile.factors`: at least 2 factors with rationale (e.g., mathematical correctness, limited consumer base).
- `[simulation]` `product_definition.vision`: specific one-sentence description mentioning colorspace conversion.
- `[simulation]` `product_definition.scope.v1`: includes specific colorspaces to support, conversion endpoint, batch endpoint, error handling.
- `[simulation]` `product_definition.scope.later`: at least 1 deferred item (e.g., public API with auth, hex string parsing, CSS color name support, ICC profile support).
- `[simulation]` `product_definition.platform`: populated (Rust, single binary).
- `[simulation]` `technical_decisions`: includes web framework choice, serialization approach, conversion architecture decision (hub-and-spoke or direct), each with rationale.
- `[simulation]` `user_expertise`: `technical_depth` at advanced or expert level.

**Must-not-do:**

- `[simulation]` Must not set `has_human_interface` to any truthy value.
- `[simulation]` Must not set risk above "medium" for an internal tool.
- `[simulation]` Must not add `handles_sensitive_data` or `has_multiple_party_types`.

**Quality criteria:**

- `[simulation]` A reader of `project-state.yaml` alone can understand: this is a Rust REST API for colorspace conversion, used internally, with no UI.
- `[simulation]` Values are specific, not generic ("REST API converting between 10 colorspaces for internal design team use" not "a developer utility").
- `[simulation]` Technical decisions reflect Rust ecosystem choices, not generic web framework decisions.

## End-to-End Success Criteria

The scenario succeeds when:

1. Starting from the input above, the system correctly detects `exposes_programmatic_interface` and does NOT detect `has_human_interface`.
2. Discovery surfaces API design concerns (endpoint structure, error handling, versioning, batch operations) and mathematical correctness concerns (precision, round-trip fidelity, gamut limitations).
3. Universal artifacts are generated with correct frontmatter, proportionate to a medium-risk internal tool.
4. API contract artifact is generated with specific endpoint definitions, request/response schemas, and error formats.
5. NO human-interface artifacts are generated (no screen specs, no design direction, no accessibility spec, no localization, no onboarding).
6. Test specifications include concrete reference values for at least 3 colorspace conversions and property-based round-trip fidelity tests.
7. The total output is proportionate — a reader should not think "this is enterprise overkill for an internal conversion tool."
8. A Rust developer reading the artifacts could begin implementing without ambiguity on API shape, colorspace coverage, error handling, or conversion architecture.
