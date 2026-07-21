---
artifact: screen-spec
version: 1
depends_on:
  - artifact: information-architecture
  - artifact: data-model
last_validated: null
---

# Screen Specifications

<!-- This artifact defines the detailed specification for every screen listed in the Information Architecture. Each screen gets a section below. For products with many screens, generate all sections into this single file (not one file per screen). -->

<!-- Modality note: For games, "Layout" describes the game view composition (play area, HUD, controls). "User Actions" includes continuous input (hold, drag, rapid tap), not just discrete button taps. For dashboards, "Layout" describes panel arrangement and data density. Adapt vocabulary to match the product type. -->

<!-- For a low-risk utility, half a page per screen is sufficient. Don't pad with implementation details. -->

<!-- === Copy the section below for each screen in the Screen Inventory === -->

## [Screen Name]

### Purpose

<!-- One sentence: why this screen exists and what the user accomplishes here. -->

### Layout

<!-- Describe the spatial arrangement of content and controls on this screen. -->
<!-- - What areas exist (header, main content, action bar, etc.)? -->
<!-- - What is the visual weight / hierarchy of each area? -->
<!-- - How does content flow (top-to-bottom, grid, etc.)? -->

<!-- For cross-platform products, describe the shared layout intent first, then note per-platform differences (native components, responsive breakpoints, touch vs. mouse). -->

### Data Displayed

<!-- What information appears on this screen? For each data element: -->
<!-- - Data element name -->
<!-- - Source entity/field from the Data Model -->
<!-- - Display format (e.g., "Player.name as text", "Score.value as large number") -->
<!-- - Update behavior (static, real-time, on-action) -->

<!-- Every data element must trace to a Data Model entity. If a data element doesn't map, the Data Model is incomplete. -->

### User Actions

<!-- What can the user do on this screen? For each action: -->
<!-- - Action name (e.g., "Submit score", "Navigate to history") -->
<!-- - Trigger (button tap, swipe, form submit, etc.) -->
<!-- - Result (what changes on this screen or where the user goes) -->
<!-- - Validation (if applicable — what input is checked and how errors appear) -->

<!-- Every action must trace to a core flow step. If an action serves no flow, question whether it belongs. -->

### States

<!-- This screen's specific states: -->
<!-- - Empty: what appears before data exists (first-run or no results) -->
<!-- - Loading: what appears while data loads (if applicable) -->
<!-- - Populated: the normal state with data present -->
<!-- - Error: what appears when something goes wrong -->
<!-- - Any screen-specific states (e.g., editing mode, selection mode) -->

### Navigation

<!-- How the user arrives at and leaves this screen: -->
<!-- - Entry points (which screens/actions lead here) -->
<!-- - Exit points (where the user can go from here) -->
<!-- - Back behavior (what "back" means from this screen) -->
