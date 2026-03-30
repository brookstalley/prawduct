# Closed-Loop Testing: Dev-Tools MCP Server Design (Web UI Specific)

Created: 2026-02-15
Phase: 2 (Design only — no implementation in this phase)
Status: Draft

> **Scope note (2026-02-18):** This document is a **web-UI-specific reference implementation** within the
> broader Agent Verification Architecture (see `docs/high-level-design.md` § Agent Verification Architecture).
> The general architecture defines verification as a principle applicable to all product types, with MCP as
> the preferred approach for web UIs and other product types using lighter strategies (Bash, process I/O).
> This design doc covers the MCP+Playwright implementation for `has_human_interface` (web) products only.

## Problem

The framework generates detailed visual specifications (Design Direction with hex colors, Typography with exact font sizes, Spacing with pixel values, Component Patterns with state specifications) but has **no mechanism to verify these specs are actually implemented in the rendered output**.

The Builder excels at code-level verification (tests pass, architecture matches, specs referenced) but is blind to visual output. For `has_human_interface` products, this means:

- Layout doesn't match screen spec → undetected
- Colors don't match Design Direction → undetected
- Responsive behavior broken → undetected
- Accessibility contrast failures → undetected
- Interactive feel (animations, transitions) → undetected

The agent compensates by asking the human to verify ("can you try this?", "what does it look like?"). This creates a human bottleneck that defeats the purpose of agent-driven development.

Framework observations have already flagged this: terminal arcade game eval explicitly marks "gameplay feel, visual rendering quality, and responsive controls" as "unable to evaluate" without interactive testing.

## Solution

Bake a dev-only MCP server into every generated `has_human_interface` product. The server exposes tools that let the agent see, drive, and inspect the UI — the same capabilities a human tester would have, but structured as MCP tools.

## Architecture

### Per-Product Generated Code

Each `has_human_interface` product gets a `dev-tools/` directory containing:

```
dev-tools/
├── server.ts          # MCP server entry point (HTTP transport)
├── browser.ts         # Playwright browser management (launch, navigate, screenshot)
├── interaction.ts     # UI interaction tools (click, type, select, scroll)
├── inspection.ts      # DOM/state inspection tools
├── accessibility.ts   # Axe-core accessibility auditing
├── package.json       # devDependencies: @modelcontextprotocol/sdk, playwright, @axe-core/playwright
└── tsconfig.json
```

The framework provides a **template** for this code. The Builder generates a customized version during the scaffold chunk, tailored to the product's specific stack (React state inspection hooks differ from Vue, etc.).

### MCP Transport: HTTP on Localhost

The server runs as an HTTP MCP server on localhost (e.g., `http://127.0.0.1:3100/mcp`). HTTP transport was chosen over stdio because:

- The Builder can start/stop the server via Bash without affecting Claude Code's process tree
- Multiple tools can query the server concurrently
- The server can manage a persistent Playwright browser session across multiple tool calls
- Matches the existing pattern seen in other projects (e.g., grasshopper MCP server)

### Lifecycle During Build

```
Scaffold chunk:
  1. Builder generates dev-tools/ directory from framework template
  2. Builder runs: npm install (installs playwright and MCP SDK as devDependencies)
  3. Builder runs: npx playwright install chromium (installs browser binary)
  4. Builder writes .mcp.json with dev-tools server config
  5. Builder starts app dev server: npm run dev (background)
  6. Builder starts MCP server: node dev-tools/server.js --app-url http://localhost:3000 --port 39427 (background)
  7. Builder registers MCP server: claude mcp add --transport http dev-tools http://127.0.0.1:39427/mcp

Each UI chunk:
  1. Builder writes tests and implementation
  2. Builder runs unit/integration tests (existing flow)
  3. Builder uses MCP tools for visual verification:
     a. navigate to relevant page/route
     b. screenshot → Claude analyzes the image against Design Direction spec
     c. get_accessibility_tree → verify structure matches screen spec
     d. accessibility_audit → verify WCAG compliance
     e. interact (click, type) → verify interactive behavior works
     f. set_viewport to mobile size → screenshot → verify responsive behavior
  4. If visual issues found, Builder fixes and re-verifies

Build completion:
  1. Full visual verification pass across all routes
  2. Accessibility audit on all pages
  3. Stop MCP server and dev server
```

## MCP Tools

### Browser Management

| Tool | Parameters | Returns | Purpose |
|------|-----------|---------|---------|
| `dev_server_start` | `command: string` | `{ url, pid }` | Start the app's dev server |
| `dev_server_stop` | — | `{ success }` | Stop the dev server |
| `set_viewport` | `width, height` | `{ success }` | Set browser viewport size |

### Navigation & Screenshots

| Tool | Parameters | Returns | Purpose |
|------|-----------|---------|---------|
| `navigate` | `url: string` | `{ title, url }` | Navigate to URL or route |
| `screenshot` | `selector?: string, fullPage?: boolean` | `{ image: base64 }` | Capture screenshot (Claude sees the image) |
| `wait_for` | `selector: string, state?: string, timeout?: number` | `{ found }` | Wait for element to appear/disappear |

### Interaction

| Tool | Parameters | Returns | Purpose |
|------|-----------|---------|---------|
| `click` | `selector?: string, text?: string, role?: string` | `{ success }` | Click element by selector, visible text, or ARIA role |
| `type_text` | `selector: string, text: string` | `{ success }` | Type text into input element |
| `select_option` | `selector: string, value: string` | `{ success }` | Select option from dropdown |
| `press_key` | `key: string` | `{ success }` | Press keyboard key (Enter, Tab, Escape, etc.) |

### Inspection

| Tool | Parameters | Returns | Purpose |
|------|-----------|---------|---------|
| `get_text` | `selector?: string` | `{ text }` | Get text content of element or page |
| `get_element_info` | `selector: string` | `{ tag, styles, attributes, bounds, accessible_name }` | Get detailed element information |
| `get_accessibility_tree` | `selector?: string` | `{ tree }` | Get accessibility tree (roles, names, states) |
| `get_console_logs` | `level?: string` | `{ logs: [{level, message, source}] }` | Get browser console output |
| `evaluate_js` | `expression: string` | `{ result }` | Execute JavaScript in page context |

### Accessibility

| Tool | Parameters | Returns | Purpose |
|------|-----------|---------|---------|
| `accessibility_audit` | `selector?: string, rules?: string[]` | `{ violations, passes, incomplete }` | Run axe-core accessibility audit |

### App State (stack-specific, generated per product)

| Tool | Parameters | Returns | Purpose |
|------|-----------|---------|---------|
| `get_app_state` | `component?: string` | `{ state }` | Inspect app state (React DevTools, Vue DevTools, etc.) |
| `seed_data` | `scenario: string` | `{ success }` | Populate test data |
| `clear_data` | — | `{ success }` | Reset app state |
| `set_config` | `key: string, value: string` | `{ success }` | Set environment variable or feature flag |

## How Claude Uses Screenshots

Claude is multimodal — it can analyze images. The verification workflow:

1. Builder takes a screenshot after implementing a UI chunk
2. Claude compares the screenshot against:
   - **Design Direction** artifact: Do colors, fonts, spacing match?
   - **Screen Spec** artifact: Are all specified elements present? Is layout correct?
   - **Accessibility Spec** artifact: Are focus indicators visible? Is text readable?
3. If discrepancies found, Builder fixes the code and retakes the screenshot
4. This loop continues until the rendered output matches the specs

This is the same loop a human tester would perform, but faster and more consistent.

## Opt-In Design

The dev-tools MCP server is **optional**. Some users may be uncomfortable with browser automation or the additional dev infrastructure. The framework must respect this.

**How it works:**
- During discovery or definition, the Orchestrator surfaces the option: "For UI products, I can set up a dev-tools server that lets me see and interact with your app directly — this means I can catch visual bugs and iterate without asking you to test. Want me to include that?"
- If the user declines, the Builder falls back to the current approach: code-level tests only, with the user as visual verifier when needed
- The `project-state.yaml` records the choice: `dev_tools.enabled: true|false`
- The Artifact Generator only includes dev-tools in the scaffold chunk if enabled
- The Critic only checks for visual verification evidence if dev-tools are enabled

**The framework never silently installs browser automation software.** This is a trust decision the user makes explicitly.

## Security Model

### Hard Rule: HR10 — No Dev Tooling in Production

The dev-tools MCP server is development infrastructure. It must NEVER be included in production builds.

**Enforcement:**
- `dev-tools/` directory is devDependency only
- Build scripts exclude `dev-tools/` from production bundles
- `.gitignore` includes `dev-tools/node_modules/` (but not `dev-tools/` itself — the code should be committed so it's reproducible)
- **Critic check:** Verify `dev-tools/` is not referenced in production build config, is not imported by production code, and is excluded from deployment artifacts

### Localhost Only, Safe Port

The MCP server binds to `127.0.0.1` only on a **non-standard, rarely-used port** (default: `39427`). This avoids conflicts with common development ports (3000, 3001, 5173, 8080, etc.) and reduces the chance of accidental exposure.

**Port selection:**
- Default: `39427` (chosen to be unlikely to conflict with any existing service)
- Configurable via `DEV_TOOLS_PORT` environment variable if the default conflicts
- The server refuses to start if the port is already in use (fail-safe, no silent fallback to another port)
- No authentication required because it's localhost-only, but the server validates that incoming connections originate from `127.0.0.1`

### Test Data Only

The `seed_data` and `clear_data` tools operate on the development database/state only. They should never be connected to production data. The Builder uses test fixtures, not real user data.

### No Credential Exposure

The MCP server does not store or transmit credentials. If the app requires authentication for testing, use test accounts with mock/development credentials that are:
- Stored in `.env.development` (not `.env.production`)
- Clearly marked as test-only
- Never committed to version control

## Technology Choices

### v1: Web (React + Playwright)

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| MCP Server | `@modelcontextprotocol/sdk` (Node.js) | Official SDK, well-supported |
| Browser Automation | Playwright | Best-in-class, headless by default, multi-browser |
| Accessibility | `@axe-core/playwright` | Industry standard, integrates with Playwright |
| State Inspection | React DevTools protocol | Stack-specific; alternatives for Vue, Svelte, etc. |

### Future Modalities

The MCP tool interface is designed to be modality-independent where possible:

| Modality | Backend | Notes |
|----------|---------|-------|
| Web (React, Vue, Svelte) | Playwright | v1 target |
| Mobile (iOS, Android) | Appium + screenshots | Same MCP interface, different backend |
| Desktop (Electron) | Playwright (Electron mode) | Playwright supports Electron natively |
| Terminal | terminal screen capture + expect-like interaction | Different tool set (no DOM) |

The key insight: the MCP tool interface (`screenshot`, `navigate`, `click`, `type_text`) is consistent across modalities. Only the backend changes.

## Framework Changes Required (Phase 3)

### 1. Builder Skill (`skills/builder/SKILL.md`)

Add a new section: **Visual Verification for UI Products**

When building `has_human_interface` products:
- Scaffold chunk includes dev-tools setup
- After each UI-touching chunk, run visual verification:
  1. Navigate to affected routes
  2. Screenshot and compare against Design Direction
  3. Run accessibility audit
  4. Test key interactions
  5. Test at multiple viewport sizes (if responsive)
- Record visual verification evidence in `build_state`

### 2. Artifact Generator (`skills/artifact-generator/SKILL.md`)

For `has_human_interface` products, Phase D (Build Planning) should:
- Include dev-tools setup in scaffold chunk deliverables
- Include visual verification steps in each UI chunk's acceptance criteria
- Add visual verification as a chunk completion requirement

### 3. Critic Skill (`skills/critic/SKILL.md`)

New check within Spec Compliance:
- For `has_human_interface` chunks: verify visual verification evidence exists
- Verify dev-tools directory is not in production build config
- Verify accessibility audit was run and has no critical violations

### 4. Principles (`docs/principles.md`)

Add: **HR10: No Dev Tooling in Production.** Development infrastructure (MCP servers, test harnesses, debug tools) is never included in production builds. The Critic verifies this.

### 5. Template (`templates/human-interface/dev-tools-spec.md`)

Template for the generated dev-tools MCP server, customized per product's stack.

### 6. Test Scenarios

Update family-utility scenario rubric:
- Must-do: Visual verification performed on at least one route
- Must-do: Accessibility audit run with no critical violations
- Quality: Screenshots referenced in verification evidence

## Open Questions

1. **Claude Code MCP reload:** Does `claude mcp add` during a session make tools available immediately, or does Claude Code need a restart? This affects whether dev-tools can be set up in the scaffold chunk and used in the next chunk within the same session. Fallback: instruct user to restart Claude Code after scaffolding.

2. **Screenshot analysis accuracy:** How reliably can Claude compare a screenshot against a Design Direction spec? This needs testing. The agent may need explicit criteria ("background should be #1a1a2e", "header font should appear ~24px") rather than holistic comparison.

3. **Non-web modalities in v1:** Should v1 include terminal UI support alongside web? Terminal UIs are simpler (text-based screenshots) but need a different backend. The terminal arcade game scenario would benefit.

4. **Performance:** Playwright adds ~200MB for browser binaries. Is this acceptable for all products? Consider making it optional for very small products.

## Implementation Sequence (Phase 3)

1. Create the dev-tools MCP server template
2. Add dev-tools generation to Artifact Generator
3. Add visual verification instructions to Builder
4. Add dev-tools Critic checks
5. Add HR10 to principles
6. Update family-utility eval rubric
7. Test end-to-end with a real product build
