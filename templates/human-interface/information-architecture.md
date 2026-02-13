---
artifact: information-architecture
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: screen-spec
  - artifact: localization-requirements
  - artifact: onboarding-spec
  - artifact: accessibility-spec
last_validated: null
---

# Information Architecture

<!-- This artifact describes the product's screen structure, navigation, and user flows. It is the UI equivalent of Pipeline Architecture for automations — it defines the system's structural skeleton. -->

<!-- Modality note: For games and interactive experiences, "screens" are game views or states (title screen, gameplay, pause menu, game over). "Navigation" is state transitions between views, not tab bars or hamburger menus. Adapt vocabulary throughout this artifact to match the product's interaction model. -->

## Screen Inventory

<!-- List every distinct screen (or view/state) in the product. For each screen: -->
<!-- - Screen name -->
<!-- - Purpose (one sentence) -->
<!-- - Primary persona(s) who use it -->
<!-- - Entry points (how the user gets here) -->
<!-- - Priority (core flow vs. supporting) -->

<!-- For a low-risk utility, this may be 4-8 screens. Don't invent screens that serve no core flow. -->

## Navigation Structure

<!-- How screens connect to each other: -->
<!-- - Primary navigation pattern (tab bar, drawer, stack, hub-and-spoke, etc.) -->
<!-- - Navigation hierarchy (which screens are top-level, which are nested) -->
<!-- - Persistent vs. contextual navigation elements -->
<!-- - Back/escape behavior -->

<!-- For cross-platform products, specify shared screen inventory first, then note per-platform navigation differences (e.g., iOS tab bar vs. web sidebar, Android back button vs. explicit back arrows). -->

## User Flows

<!-- For each core flow from the Product Brief, describe the screen sequence: -->
<!-- - Starting screen -->
<!-- - User actions at each step -->
<!-- - Screen transitions -->
<!-- - Ending screen / completion state -->

<!-- Every core flow must trace through specific screens. If a flow can't be mapped to screens, the Screen Inventory is incomplete. -->

## Information Hierarchy

<!-- What information is most important on each screen? -->
<!-- - Primary content (what the user came here to see/do) -->
<!-- - Secondary content (supporting information) -->
<!-- - Actions (what the user can do) -->
<!-- - Status indicators (system state, feedback) -->

<!-- This drives layout decisions in the Screen Spec. If everything is "primary," nothing is. -->

## Screen States

<!-- Every screen has multiple states. At minimum, identify: -->
<!-- - Empty state: what the user sees before any data exists -->
<!-- - Loading state: what the user sees while data loads -->
<!-- - Populated state: the normal, data-present view -->
<!-- - Error state: what the user sees when something goes wrong -->

<!-- Not every screen needs all four states (a settings screen may not have a loading state), but the assessment must be explicit. -->

## Boundaries

<!-- What this product's interface does NOT include. Explicit boundaries prevent scope creep during screen design. -->
<!-- Examples: "No admin interface in v1," "No web version," "No landscape mode." -->
