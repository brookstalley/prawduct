# Test Scenario: Terminal Arcade Game

## Prerequisites

**This scenario requires tier-2 framework capabilities:**
- Discovery surfaces UI concerns with dynamic domain depth for Entertainment
- Planning supports universal artifacts with game/real-time architecture awareness
- Review Perspectives evaluate non-web UI concerns (terminal rendering, game loop architecture, text-based visual design)
- Building can execute build plans for real-time terminal applications
- Critic can evaluate game-specific build quality (game loop performance, input responsiveness)

**Additional framework stretch:**
- This scenario tests the framework's ability to handle an unusual UI substrate (terminal/TUI rather than web or mobile). The discovery methodology's UI guidance assumes web/mobile in several places. This scenario reveals where those assumptions are baked in vs. where general principles adapt naturally.
- The Entertainment dynamic domain depth relies on LLM knowledge rather than hardcoded question banks. This scenario exercises it more deeply than the family-utility scenario (which is Entertainment/Utility, not pure Entertainment).

**Current status**: Ready for tier-2 evaluation. All required capabilities are implemented. Terminal-specific adaptations may surface framework gaps — this is a feature, not a bug. Observations from this scenario should feed back into skill improvements.

---

## Scenario Overview

- **Primary structural:** `has_human_interface` (modality: terminal)
- **Domain:** Entertainment
- **Risk Level:** Low-Medium
- **Evaluation tier:** 2 (structural characteristic + domain diversity)
- **Purpose:** Tests framework behavior with an unusual UI substrate (terminal, not web/mobile), real-time game loop architecture, cross-platform terminal compatibility, and entertainment domain handling. Exercises whether the system can bring game design expertise to a technical user who defers on design. Validates that the framework recognizes degenerate artifacts (security, ops) while taking genuine technical complexity seriously (real-time input, rendering, terminal abstraction).

## Why This Scenario Is Challenging

This scenario creates productive tension across multiple framework dimensions:

1. **Unusual platform.** The framework's UI Application handling assumes web or mobile. A terminal game breaks those assumptions — no CSS, no touch targets, no responsive web layout, no browser APIs. The system must adapt without shoehorning terminal concepts into web concepts.

2. **Real-time architecture.** Most products the framework handles are request-response (web apps, APIs, pipelines). A game loop is fundamentally different: continuous rendering, non-blocking input, frame timing, entity updates per tick. The system must recognize this as an architectural paradigm shift, not just a feature.

3. **Cross-platform terminal abstraction.** "Runs anywhere" means handling terminal differences across operating systems (ANSI escape codes, key sequences, color support, Unicode support, resize signals). This is a genuine technical complexity that the system must surface and address.

4. **Game design as a domain.** The test persona is a strong developer but not a game designer. The framework must bring game design expertise: difficulty curves, scoring feel, visual feedback, game states (title, playing, paused, game over), wave progression, enemy behavior. This tests the "Bring Expertise, Don't Just Extract Requirements" principle.

5. **Testing real-time systems.** How do you write unit tests for collision detection, frame rendering, and input processing in a game loop? The test specifications must address this — it's fundamentally different from testing CRUD or API endpoints.

6. **Degenerate artifacts.** Security model and operational spec should be minimal for a local-only, single-player terminal game. The framework should recognize this and not pad content. But terminal compatibility concerns ARE real operational concerns the system must surface.

7. **Color accessibility tension.** The game uses ANSI colors, but some terminals have limited color support, and colorblind users exist. The framework should surface this without over-engineering the solution.

8. **Dynamic resizing.** The user explicitly wants the game window to adapt when the terminal is resized during play. This is a real constraint that affects rendering architecture, game boundary calculations, and entity positioning.

9. **Proportionality pressure.** This is a fun side project, not enterprise software. But the technical complexity is genuinely medium. The system must be proportionate without trivializing the real challenges.

## Test Persona

**Name:** Jordan Reyes

**Background:** Senior software engineer with 8+ years of experience, currently at a mid-size tech company. Strong backend and systems programming background. Grew up playing arcade games and has nostalgia for the genre. Has built small CLI tools and utilities before but never a real-time game. Comfortable with terminals, ANSI escape codes, and cross-platform development concepts.

**Technical expertise:**
- Deep comfort with programming languages, build tools, testing frameworks
- Understands game concepts (game loops, collision detection, frame rates) at a conceptual level but hasn't implemented them
- Familiar with terminal capabilities (colors, cursor positioning, alternate screen buffer)
- Knows cross-platform compatibility is hard but hasn't wrestled with terminal differences specifically
- No game design background — knows what "feels fun" when playing but hasn't designed difficulty curves or scoring systems

**Communication style:**
- Uses technical jargon comfortably and precisely
- Gives clear, opinionated answers on platform and controls
- Defers on game design decisions with genuine trust: "you know games better than I do"
- Pragmatic — wants a fun, working game, not a perfect one
- Slightly impatient with process but respects good questions

**Current motivation:** Weekend project. Wants something fun to hack on and show friends. No commercial intent. The cross-platform and "all text" constraints are deliberate creative constraints, not limitations.

## Evaluation Procedure

### Setup

1. Create an isolated project directory for the evaluation:
   ```bash
   python3 tools/prawduct-setup.py setup /tmp/eval-terminal-arcade --name "Terminal Invaders"
   ```

### Running the evaluation

3. Start a new LLM conversation in `/tmp/eval-terminal-arcade`. The generated repo is self-contained (own CLAUDE.md, hooks, Critic instructions).
4. Send the Input prompt (below) as the user's opening message.
5. For each system question, respond using the scripted Test Conversation responses below. If the system asks about a topic not covered, respond in character as Jordan Reyes (see Test Persona).
6. Let the system run through Stages 0 → 0.5 → 1 → 2 → 3.

### Evaluating results

7. After the run completes, evaluate against the Evaluation Rubric (below) by checking:
   - `/tmp/eval-terminal-arcade/project-state.yaml` against the C5 criteria
   - `/tmp/eval-terminal-arcade/artifacts/*.md` against the C3 criteria
   - The conversation transcript against C1, C2, and C4 criteria
8. Record pass/fail for each must-do, must-not-do, and quality criterion.

### Recording results

9. **Before cleanup**, record evaluation results. Include: scenario name, date, framework version (git SHA), pass/fail per rubric criterion with evidence, and issues found.

### Cleanup

10. Delete the evaluation directory when done:
    ```bash
    rm -rf /tmp/eval-terminal-arcade
    ```

## Input

> "I want to build a text-based arcade shooter like Galaga that runs in the terminal. Pure text — colored characters and symbols, no graphics. Arrow keys to move, space to fire. It needs to work on any terminal and the game area should resize when you resize the window."

The input signals:
- UI Application (but terminal, not web or mobile)
- Entertainment domain (arcade game)
- Technical user (specific technical vocabulary: "terminal," "ANSI," "resize")
- Clear platform constraint (terminal, cross-platform)
- Clear interaction model (arrow keys + space)
- Clear visual constraint (text-only, colored characters)
- Specific requirement (dynamic resizing)
- Reference to a known game (Galaga) providing an implicit spec for core gameplay

## Test Conversation

To ensure repeatable evaluation, the following scripted responses define what Jordan Reyes says when asked about each topic. The evaluator provides these responses regardless of how the system phrases its questions. If the system doesn't ask about a topic (e.g., because it infers the answer), the corresponding response is not volunteered.

**When asked to confirm classification or assumptions:**
> "Yeah, that's right."
>
> Accept reasonable inferences. Correct only if the system makes a clearly wrong assumption.

**When asked about users / who plays it:**
> "Just me and anyone I share the repo with. It's a side project — no distribution beyond 'clone it and run it.'"

**When asked about what makes it fun / core gameplay:**
> "The Galaga loop: enemies come in formation, they swoop down at you, you dodge and shoot. Simple mechanics but satisfying when the patterns get tricky and your reflexes kick in. I want that 'one more round' feeling."

**When asked about platform / where it runs:**
> "Any terminal. macOS Terminal, iTerm, Linux xterm/gnome-terminal, Windows Terminal, even basic SSH sessions. I want someone to be able to clone the repo, run one command, and play."

**When asked about controls / input:**
> "Arrow keys left and right to move your ship. Space to fire. That's it. Maybe 'q' to quit and 'p' to pause, but keep it minimal."

**When asked about the game name:**
> "I've been thinking of calling it 'Terminal Invaders' — kind of a nod to Space Invaders but with the terminal twist. Open to other ideas though."

**When asked about visual approach / graphics:**
> "All text. The ship could be something like `^` or `▲`, enemies could be different characters depending on type, bullets are `|` or `·`. Use ANSI colors — green for the player, red for enemies, yellow for bullets, whatever looks good. The frame border could be box-drawing characters. I trust your judgment on the specifics."

**When asked about terminal resizing:**
> "Yeah, if I drag the terminal window bigger or smaller while playing, the game area should adapt. Don't want the game to break or look weird if the window size changes."

**When asked about difficulty / progression / game design:**
> "I haven't thought that through. I know I want waves of enemies that get progressively harder. You probably know more about what makes this feel right than I do — I trust you to design the progression."

**When asked about scoring:**
> "Sure, a score. Points for killing enemies, bonus for clearing a wave. I'm flexible on the details."

**When asked about lives / game over:**
> "Classic arcade — you get a few lives, lose one when hit, game over when they're gone. Standard stuff."

**When asked about enemy behavior / patterns:**
> "Like Galaga — they start in formation at the top, then some swoop down in patterns. I'd love different enemy types with different behaviors but I'm flexible on exactly what those are."

**When asked about sound / audio:**
> "No audio. Pure visual. Terminal beeps are annoying and most terminals handle them differently anyway."

**When asked about persistence / saving:**
> "Not for v1. Just play and see your score at the end. We can add high scores later if it's fun."

**When asked about multiplayer:**
> "No. Single player only."

**When asked about technology / language preference:**
> "I'm open. Whatever has the best cross-platform terminal library situation. I've used Node and Python a lot, but I'll use whatever makes sense."

**When asked about dependencies / external services:**
> "None. This should be fully offline, no network calls. Just a terminal app."

**When asked about performance / frame rate:**
> "It needs to feel smooth. If there's visible lag or stutter, it breaks the game feel. I don't need 120fps but it should feel responsive."

**When asked about color fallback / terminal compatibility:**
> "Good question. I'd prefer it gracefully degrades — if a terminal can't do 256 colors, use basic 16. If it can't do colors at all, it should still be playable in monochrome. But I don't need to support ancient terminals."

**When asked about anything not covered above:**
> Give a brief, technically-informed answer consistent with Jordan Reyes's persona: a knowledgeable developer who has clear opinions on technical constraints but defers on game design. If asked about game design specifics (level design, enemy patterns, scoring formula, difficulty tuning), defer: "Whatever you think works. I trust the design."

**General persona behavior:**
- Uses technical terms accurately and expects the system to match
- Opinionated on platform, controls, and visual constraints
- Genuinely defers on game design — not being lazy, but recognizing it's not their expertise
- Slightly impatient: doesn't want to answer 15 questions about a weekend game project
- Cooperative and enthusiastic about the project itself

## Test Conversation (Build — Stages 4-6)

These scripted responses extend the test conversation for the build stages.

**When asked to confirm the build plan:**
> "Looks good. Let's build it."

**When shown progress during building (chunk completion messages):**
> [No response needed. Accept silently unless the system explicitly asks a question.]

**When the system surfaces an implementation issue (artifact insufficiency or spec ambiguity):**
> "What do you recommend?"
>
> Accept the system's recommendation. Jordan trusts technical judgment on implementation details.

**When presented with the working game and asked to try it:**
> "This is great! Really fun. One thing — can you add a persistent high score board? Top 10 scores saved between sessions. I want to compete against myself."

**When asked about additional changes after the high score iteration:**
> "Nope, this is awesome. Ship it."

**General persona (continued):** Same as Stages 0-3 — technically precise, defers on game design, enthusiastic.

## Evaluation Rubric

### Discovery (C2)

**Must-do:**

- `[simulation]` Detect `has_human_interface` structural characteristic with modality `terminal` (the system should recognize this is a terminal application, not a web or mobile UI).
- `[simulation]` Classify domain as Entertainment (Game also acceptable).
- `[simulation]` Assign low or low-medium risk profile (technical complexity of real-time game loop warrants medium on that factor, but low user count, no data sensitivity, no regulatory exposure).
- `[interactive]` Ask about or infer core gameplay (what happens in the game — the "Galaga loop").
- `[interactive]` Ask about or infer platform constraints (which terminals, what compatibility level).
- `[interactive]` Surface game design considerations the user hasn't specified (difficulty progression, wave design, scoring feel, game states like title/pause/game-over).
- `[interactive]` Surface cross-platform terminal compatibility as a technical consideration (different terminals have different capabilities).
- `[simulation]` Limit total discovery questions to 8-12 for this risk level.

**Must-not-do:**

- `[simulation]` Must not detect `runs_unattended` or `exposes_programmatic_interface` structural characteristics.
- `[interactive]` Must not ask about authentication, authorization, or user accounts.
- `[interactive]` Must not ask about deployment infrastructure, monitoring, or alerting (this is a local terminal app).
- `[interactive]` Must not ask about regulatory or compliance requirements.
- `[interactive]` Must not ask about data privacy or GDPR.
- `[interactive]` Must not ask about API contracts, webhooks, or integrations.
- `[interactive]` Must not ask about scalability or load handling.
- `[interactive]` Must not recommend not building this.
- `[interactive]` Must not spend more than 2 turns researching existing terminal games or game libraries.
- `[simulation]` Must not generate more than 15 discovery questions total.
- `[interactive]` Must not ask the user to self-assess their technical expertise.

**Quality criteria:**

- `[interactive]` Questions recognize and engage with the user's technical expertise — use appropriate terminology, don't explain what a terminal is.
- `[interactive]` Questions bring game design expertise the user lacks — difficulty curves, visual feedback, game state management, "juice" (the small details that make games feel good).
- `[interactive]` Inferences are made about obvious decisions (single-player, no network, no persistent storage in v1) and confirmed rather than asked as open questions.
- `[interactive]` Prior art awareness surfaces relevant terminal game libraries and existing terminal arcade games as expertise. Acknowledges the space exists (terminal games are a known genre) but respects Jordan's choice to build from scratch as a creative exercise. For low-medium risk, 2-3 searches is proportionate.
- `[interactive]` The discovery conversation surfaces the real technical challenge (cross-platform terminal I/O, real-time input handling, resize events) without making it sound scary.

### Session Management (C1)

**Must-do:**

- `[interactive]` Progress through stages 0 → 0.5 → 1 → 2 without excessive back-and-forth.
- `[simulation]` Infer technical user from input vocabulary ("terminal," resize, arrow keys, ANSI).
- `[interactive]` Use technical terminology naturally and at the user's level.
- `[interactive]` Recognize the unusual platform (terminal game, not web/mobile) and adapt accordingly — not shoehorn terminal concepts into web concepts.
- `[interactive]` Make reasonable assumptions and state them explicitly (single-player, offline-only, no persistence in v1, no audio).
- `[interactive]` Recognize that game design expertise is needed and proactively provide it (difficulty curves, scoring, game states).
- `[interactive]` Recognize when discovery is "good enough" — this is a low-risk fun project and the developer wants to build.

**Must-not-do:**

- `[simulation]` Must not conduct more than 2-3 rounds of discovery questions for this risk level.
- `[interactive]` Must not over-explain terminal or programming concepts to this technical user.
- `[interactive]` Must not treat this like a web application (no discussion of responsive CSS, mobile breakpoints, PWA, etc.).
- `[interactive]` Must not ask the user to choose between game design alternatives they haven't thought about — make recommendations and let them react.
- `[interactive]` Must not make the process feel heavyweight for a weekend game project.

**Quality criteria:**

- `[interactive]` Vocabulary matches the user's technical level (developer-to-developer conversation).
- `[interactive]` Discovery completes in 2-3 question rounds — explores the real unknowns (game design, terminal compatibility) without belaboring the obvious (it's a game, it runs in a terminal).
- `[interactive]` The system proactively contributes game design thinking the user defers on.
- `[interactive]` Stage transitions happen naturally. The user shouldn't feel interrogated.
- `[interactive]` The conversation acknowledges this is a fun creative project, not enterprise software.

### Planning (C3)

**Must-do:**

- `[simulation]` Produce all 7 universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, dependency manifest.
- `[simulation]` All artifacts have correct YAML frontmatter with dependency declarations.
- `[simulation]` **Product Brief** captures the game's core loop (move, shoot, dodge, survive waves), the "one more round" engagement model, and the creative constraints (text-only, terminal, cross-platform).
- `[simulation]` **Data Model** includes game entities appropriate to an arcade shooter: at minimum Player/Ship (position, lives, score), Enemy (position, type, behavior pattern, health), Bullet/Projectile (position, direction, owner), Wave/Level (enemies, formation, difficulty parameters), and GameState (current state, score, lives, wave number). Entities must model real-time properties (position as coordinates, movement vectors or speeds).
- `[simulation]` **Security Model** is minimal/degenerate — a local single-player terminal game has no authentication, no data privacy concerns, no network attack surface. The artifact should be generated but acknowledge this is a degenerate case (proportionality assessment — Principle 10). Any residual concerns (e.g., file write for future high scores) should be noted.
- `[simulation]` **Test Specifications** include concrete scenarios for game systems: collision detection (bullet hits enemy, enemy hits player, boundary collisions), input handling (arrow key movement, firing, pause), rendering (screen update, resize handling), game state transitions (title → playing → paused → game over), wave progression, and scoring. Tests must address how to test real-time game systems — likely through abstraction/mocking of the game loop.
- `[simulation]` **NFRs** address frame rate/rendering performance (smooth gameplay feel), input responsiveness (no perceptible input lag), startup time (fast launch), terminal compatibility (minimum terminal size, color support tiers), and memory usage (shouldn't grow unbounded during play).
- `[simulation]` **Operational Spec** is minimal — this is a local app with no server, no deployment infrastructure, no monitoring. Should address: how to install and run (one command), minimum system requirements, graceful handling of unsupported terminals.
- `[simulation]` **Dependency Manifest** includes a cross-platform terminal library (e.g., blessed, terminal-kit, crossterm equivalent) with justification for the choice, and any other needed libraries. Must justify why each dependency is needed. Should be minimal — a terminal game shouldn't need 30 packages.

**Must-not-do:**

- `[simulation]` Must not generate human-interface-specific artifacts (information architecture, screen specs, design direction for web/mobile, accessibility spec written for web).
- `[simulation]` Must not generate Automation/Pipeline or API/Service artifacts.
- `[simulation]` Must not over-engineer the security model (no OAuth, no RBAC, no session management for a single-player local game).
- `[simulation]` Must not specify web-centric NFRs (page load times, API response times, CDN caching).
- `[simulation]` Must not specify enterprise-grade operational requirements (monitoring dashboards, alerting rules, incident response) for a local terminal game.
- `[simulation]` Must not include network-dependent dependencies (no HTTP clients, no database drivers, no cloud services).

**Quality criteria:**

- `[simulation]` Artifacts are internally consistent (entities in data model appear in test specs, game states in product brief match data model state machines).
- `[simulation]` Cross-references between artifacts are accurate.
- `[simulation]` The data model captures the real-time nature of the game — positions, velocities, timing. Not just static CRUD entities.
- `[simulation]` Test specifications address the genuine difficulty of testing real-time game systems — they propose an abstraction or mocking strategy, not just "test that the game works."
- `[simulation]` NFRs feel right for a terminal game — frame rate targets, input latency, terminal compatibility — not web or mobile metrics.
- `[simulation]` A coding agent reading these artifacts would understand they're building a real-time game loop, not a request-response application.
- `[simulation]` Total artifact pages 6-12 for low-medium risk; security and operational specs each under 1 page.

### Review Perspectives (C4)

**Must-do:**

- `[simulation]` **Product perspective:** Confirms this is a real (if niche) desire — terminal games are fun to build and play. Scope is appropriate for a weekend project. Validates that the "Galaga feel" is captured in the product brief.
- `[simulation]` **Design perspective:** Evaluates the text-based visual design: Are game states clear to the player? Is the game area layout readable? Are different entity types visually distinguishable? Is color used effectively? Addresses terminal color accessibility (colorblind users, monochrome terminals, limited-color terminals). Evaluates first-run/title screen experience and game over state. Does NOT evaluate web/mobile design concerns.
- `[simulation]` **Architecture perspective:** Evaluates game loop architecture (fixed timestep vs variable, update-render separation). Evaluates terminal abstraction strategy (how to handle cross-platform differences). Evaluates resize handling (how game boundaries and entity positions adapt). Raises the input model (non-blocking keyboard input in a terminal is platform-specific and architecturally significant).
- `[simulation]` **Skeptic perspective:** Raises at least two realistic concerns from this set: What happens when the terminal is too small to play? What happens on terminals with no color support? How does the game handle key repeat rates (holding arrow keys)? What happens if resize occurs mid-collision-check? What about terminals with slow rendering (SSH over slow connection)?
- `[simulation]` Each finding has a specific recommendation, not just an observation.
- `[simulation]` Each finding has a severity level (blocking / warning / note).

**Must-not-do:**

- `[simulation]` Must not raise web-specific concerns (responsive CSS, browser compatibility, touch targets, WCAG color contrast ratios as applied to web).
- `[simulation]` Must not raise concerns about server infrastructure, database performance, or API design.
- `[simulation]` Must not raise concerns about multi-user access or data privacy.
- `[simulation]` Must not block on concerns disproportionate to the risk level (don't demand comprehensive accessibility testing for a terminal game side project).
- `[simulation]` Must not produce vague findings ("consider the user experience" or "think about performance").

**Quality criteria:**

- `[simulation]` Findings demonstrate understanding that this is a terminal game, not a web app — terminal-specific concerns are raised (ANSI escape code compatibility, alternate screen buffer, raw mode input).
- `[simulation]` Architecture findings address the real-time game loop, not request-response patterns.
- `[simulation]` Design findings address text-based visual design, not CSS or layout frameworks.
- `[simulation]` Skeptic findings are concrete and terminal-game-specific (not generic "what if it crashes").
- `[simulation]` Severity ratings are proportionate — a color fallback gap is a warning, not a blocker, for a side project.
- `[simulation]` Total findings in the 8-15 range for low-medium risk.

### Project State (C5)

The rubric evaluates the resulting `project-state.yaml` after the full process (Stages 0-2).

**Must-do (structural):**

- `[simulation]` All populated fields use correct types per the template schema.
- `[simulation]` No fields added that don't exist in the template schema.
- `[simulation]` Risk factors include rationale, not just a level.

**Must-do (content after Stages 0-2):**

- `[simulation]` `classification.domain`: "entertainment" (or "entertainment/gaming").
- `[simulation]` `classification.structural.has_human_interface`: not null, with modality "terminal".
- `[simulation]` `classification.risk_profile.overall`: "low" or "medium" (either acceptable if rationale is sound; "low" with technical-complexity factor at "medium" is ideal).
- `[simulation]` `classification.risk_profile.factors`: at least 3 evaluated factors with rationale. Must include `technical-complexity` rated medium (real-time game loop, cross-platform terminal I/O), `user-count` rated low, and `data-sensitivity` rated low.
- `[simulation]` `product_definition.vision`: a clear one-sentence description capturing the game's identity (not generic — should mention terminal, arcade, text-based).
- `[simulation]` `product_definition.users.personas`: at least one persona (the developer-player, or a general "terminal gamer" persona).
- `[simulation]` `product_definition.core_flows`: at least 3 flows: playing a game (move, shoot, survive), game lifecycle (start → play → game over → restart), and wave progression (enemies spawn, attack, clear wave, next wave). These are game loops, not CRUD operations.
- `[simulation]` `product_definition.scope.v1`: at least 5 items (core gameplay loop, wave progression, scoring, multiple enemy types, terminal resize handling).
- `[simulation]` `product_definition.scope.later`: at least 1 item explicitly deferred (high score persistence, power-ups, additional game modes, or similar).
- `[simulation]` `product_definition.platform`: "terminal/CLI" or "cross-platform terminal" (NOT "web" or "mobile").
- `[simulation]` `product_definition.nonfunctional`: frame rate / rendering performance, input responsiveness, and terminal compatibility addressed. Not web-centric metrics.
- `[simulation]` `technical_decisions`: at least one programming language/runtime decision, one terminal library decision, and one game loop architecture decision, each with rationale and alternatives considered.
- `[simulation]` `design_decisions.accessibility_approach`: addresses terminal color accessibility (color fallback for limited terminals, visual distinguishability without color). NOT web accessibility (WCAG, screen readers are not applicable to a real-time terminal game).
- `[simulation]` `user_expertise`: `technical_depth` at advanced (the user is a senior developer), `product_thinking` at basic-intermediate (they know what they want but defer on design details), `domain_knowledge` at basic or intermediate (persona references Galaga mechanics accurately but lacks game design expertise).
- `[simulation]` `current_stage`: "definition" or later.
- `[simulation]` `change_log`: at least 1 entry (initial classification).

**Must-not-do:**

- `[simulation]` Must not leave `classification.structural` with no active structural characteristics after Stage 0.
- `[simulation]` Must not detect `runs_unattended`, `exposes_programmatic_interface`, or `has_multiple_party_types` structural characteristics.
- `[simulation]` Must not add regulatory constraints for this scenario.
- `[simulation]` Must not set `risk_profile.overall` above "medium" for this scenario.
- `[simulation]` Must not set `platform` to "web" or "mobile."
- `[simulation]` Must not reference web or mobile technologies in `technical_decisions`.

**Quality criteria:**

- `[simulation]` A reader of `project-state.yaml` alone — without seeing the conversation — can understand this is a terminal-based arcade shooter, not a web app.
- `[simulation]` Values are specific, not generic ("text-based Galaga-style arcade shooter for cross-platform terminals" not "an entertainment application").
- `[simulation]` Core flows describe game mechanics and game state transitions, not CRUD operations.
- `[simulation]` Technical decisions reflect the real challenges of this product (terminal I/O, game loop, cross-platform compatibility).
- `[simulation]` Scope decisions reflect the conversation (core gameplay in v1, persistence and extras deferred).

### Build Plan (Stage 4)

**Must-do:**

- `[simulation]` Generate a build plan with at least 5 chunks (scaffold + game loop + at least 3 game system chunks).
- `[simulation]` The chunking respects game architecture: game loop/rendering must come before gameplay features that depend on it.
- `[simulation]` Scaffolding chunk specifies exact initialization commands and includes the terminal library.
- `[simulation]` A "game loop and rendering" chunk establishes the core architecture: game loop with fixed timestep, terminal setup (alternate screen, raw mode), basic rendering pipeline, and resize handling. This is the architectural foundation — everything else builds on it.
- `[simulation]` Feature chunks cover: player movement and shooting, enemy spawning and behavior, collision detection and scoring, wave progression and difficulty.
- `[simulation]` Each chunk has acceptance criteria traceable to test specification scenarios.
- `[simulation]` Early feedback milestone identified — player should be able to see and control their ship by chunk 3 or earlier.
- `[simulation]` Governance checkpoints include at least one mid-build and one final review.

**Must-not-do:**

- `[simulation]` Must not produce more than 10 chunks for this project (it's a fun side project, not a AAA game).
- `[simulation]` Must not require the user to make technology decisions at this stage.
- `[simulation]` Must not include chunks for features not in v1 scope (no high score persistence chunk, no multiplayer chunk).
- `[simulation]` Must not order game feature chunks before the game loop/rendering foundation is established.

**Quality criteria:**

- `[simulation]` Chunk ordering reflects game development realities: engine/loop first, then entities, then gameplay features.
- `[simulation]` The early feedback milestone lets the user move a character on screen early — this is motivating and validates the architecture.
- `[simulation]` A Builder reading this plan understands it's building a game loop, not a web app. The plan's language is game-development-aware.
- `[simulation]` The plan is proportionate — enough structure for quality, not so much that it feels like building a commercial game engine.

### Builder (Stage 5)

**Must-do:**

- `[simulation]` Scaffold chunk works: the specified run command starts the app, the test command runs.
- `[simulation]` The game loop runs at a consistent frame rate in the terminal (not spinning the CPU at 100%, not rendering at 2fps).
- `[simulation]` Player ship renders on screen (verifiable via test assertion or code inspection showing render function) and responds to arrow key input.
- `[simulation]` Enemies spawn in formation and exhibit at least basic movement patterns.
- `[simulation]` Bullets fire from the player ship and travel upward. Enemy bullets travel downward (if enemy shooting is in v1 scope).
- `[simulation]` Collision detection works: bullets destroy enemies, enemies (or enemy bullets) destroy the player.
- `[simulation]` Score increments when enemies are destroyed and displays on screen.
- `[simulation]` Game states work: the player can start a game, play, see game over, and restart.
- `[simulation]` Wave progression works: clearing all enemies advances to a new wave with increased difficulty.
- `[simulation]` Terminal resize during gameplay adapts the game area (doesn't crash, doesn't corrupt display).
- `[simulation]` Tests are written alongside each chunk, not all at the end.
- `[simulation]` All tests pass after every chunk.
- `[simulation]` The game runs cross-platform (or the terminal library provides cross-platform support and the code doesn't use platform-specific APIs outside the library).

**Must-not-do:**

- `[simulation]` Must not choose technologies not specified in the build plan or dependency manifest.
- `[simulation]` Must not add features not in the chunk deliverables (no high scores, no power-ups unless in v1 scope).
- `[simulation]` Must not delete or weaken tests from previous chunks.
- `[simulation]` Must not skip writing tests for a feature chunk.
- `[simulation]` Must not use platform-specific terminal calls outside the terminal abstraction library.

**Quality criteria:**

- `[simulation]` Game loop maintains 15+ FPS (measured by frame timing in tests or observing terminal output), controls respond within 1 frame, and enemies exhibit distinct movement patterns.
- `[simulation]` Code architecture reflects a real-time game (game loop, update/render separation, entity management), not a web app retrofitted into a terminal.
- `[simulation]` Test strategy handles the real-time nature of the game: game logic is testable separately from rendering, collision detection is tested with specific coordinates, game state transitions are tested.
- `[simulation]` Code complexity is proportionate — clean, not over-abstracted, not enterprise-patterned.

### Critic Product Governance (Stage 5)

**Must-do:**

- `[simulation]` Critic review runs after each feature chunk (scaffold exempt from full review).
- `[simulation]` Test count never decreases between chunks.
- `[simulation]` All core flows from the Product Brief have implementation evidence in the Critic's review.
- `[simulation]` Critic actively reviews each feature chunk with at least 2 specific findings per chunk (any severity), each referencing specific code or artifact locations.
- `[simulation]` Critic review was invoked automatically as part of the process, not prompted by user request. The system must not ask "Want me to run the Critic?" — it runs it proactively.
- `[simulation]` Fix-by-fudging detection is active: if a test is weakened to pass, the Critic catches it.

**Must-not-do:**

- `[simulation]` Must not produce more than 5 findings per chunk for this low-medium risk product.
- `[simulation]` Must not block on web/mobile concerns that don't apply to a terminal game.
- `[simulation]` Must not approve a chunk where game loop performance is clearly inadequate without flagging.

**Quality criteria:**

- `[simulation]` Findings are game-relevant (collision edge cases, rendering issues, input handling concerns), not web-app-relevant.
- `[simulation]` The review cycle converges: blocking findings → fix → re-review → clear. Not infinite loops.
- `[simulation]` Critic produces no more than 5 findings per chunk and review cycle converges within 2 iterations.

### Iteration (Stage 6)

**Must-do:**

- `[simulation]` High score board request ("persistent high score board, top 10, saved between sessions") is classified as **functional** (adds data persistence, file I/O, a new display view, and game-over flow changes).
- `[simulation]` Change impact assessment identifies affected artifacts: at minimum data-model (HighScore entity, file persistence), test-specifications (high score scenarios), and build-plan (new chunk).
- `[simulation]` Affected artifacts are updated before implementation (data model gets HighScore entity with name/score/date/wave fields, test specs get high score scenarios).
- `[simulation]` Data persistence uses local file storage (JSON file or similar) — proportionate for a local terminal game.
- `[simulation]` New tests written: saving a high score, loading existing scores, top-10 sorting, display formatting, handling missing/corrupt score file gracefully.
- `[simulation]` Existing tests still pass (no regressions).
- `[simulation]` The high score board works: scores save after game over, persist between sessions, display in sorted order.

**Must-not-do:**

- `[simulation]` Must not classify the high score request as cosmetic (it adds persistence, a new entity, and new behavior).
- `[simulation]` Must not classify it as directional (it's an additive feature, not a product pivot).
- `[simulation]` Must not implement with a database or external service (overkill for a local game — local file is proportionate).
- `[simulation]` Must not break existing gameplay, controls, or rendering.
- `[simulation]` Must not add network features or cloud storage.

**Quality criteria:**

- `[simulation]` The iteration cycle is efficient: one round of artifact update → build → review → done.
- `[simulation]` The file persistence approach is cross-platform (file paths work on macOS, Linux, Windows).
- `[simulation]` The high score display integrates naturally into the game flow (shown at game over, accessible from title screen or similar).
- `[simulation]` Iteration completes in one artifact-update → build → review cycle.

## End-to-End Success Criteria

The scenario succeeds when:

**Stages 0-3:**

1. Starting from the input above, the system correctly classifies this as a terminal-based entertainment product and calibrates to a technical user who defers on game design.
2. Discovery surfaces the real challenges (cross-platform terminal I/O, real-time game loop, game design) without wasting time on inapplicable concerns (web design, authentication, API contracts, monitoring infrastructure).
3. The system proactively contributes game design expertise: difficulty curves, enemy behavior design, visual feedback, game states. The user should feel like the system added creative value, not just extracted requirements.
4. All 7 universal artifacts are generated with correct frontmatter and internal consistency. Security model and operational spec are appropriately minimal. Data model and test specs reflect real-time game architecture, not CRUD patterns.
5. Review Perspectives produce terminal-game-specific findings: terminal compatibility, game loop architecture, text-based visual design, input handling. NOT web/mobile findings.
6. The total output is proportionate — thorough on the genuinely complex aspects (game loop, terminal I/O, game design), minimal on the degenerate aspects (security, ops, auth).
7. A coding agent reading the output would understand they're building a real-time terminal game and have clear, unambiguous specifications for game entities, game states, input handling, rendering, and cross-platform compatibility.

**Stages 4-6:**

8. Build plan translates game specifications into game-development-aware chunks: engine first, then entities, then features.
9. The game builds, runs, and is playable in the terminal. Controls are responsive. Enemies move. Bullets hit things. Score works.
10. All tests pass and test strategy handles real-time game testing appropriately (logic tests, not screenshot tests).
11. Terminal resize during gameplay works without crashing or corrupting the display.
12. The Critic reviewed each chunk with game-relevant findings.
13. High score persistence handled in one iteration cycle without regressions.
14. At least one learning captured during the process.
15. The framework recognized and adapted to the unusual platform (terminal) — it didn't try to build a web app in a terminal or apply web-centric patterns to a game.
16. Process was proportionate to a fun side project with genuine technical depth.
