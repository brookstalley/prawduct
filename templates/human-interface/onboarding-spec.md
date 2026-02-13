---
artifact: onboarding-spec
version: 1
depends_on:
  - artifact: information-architecture
  - artifact: screen-spec
  - artifact: design-direction
depended_on_by:
  - artifact: test-specifications
last_validated: null
---

# Onboarding Specification

<!-- This artifact defines how new users learn to use the product and how returning users re-engage. Onboarding is a core flow, not an afterthought — every permission request must specify what happens when denied. -->

<!-- For a low-risk utility, half a page is sufficient. A simple utility may need nothing more than a clear empty state and one explanatory screen. Don't design a tutorial system for a three-screen app. -->

## First-Run Experience

<!-- What happens when the user opens the product for the first time: -->
<!-- - Welcome screen or splash (if any) -->
<!-- - Account creation / identification (if applicable) -->
<!-- - Initial setup steps (configuration, preferences, data import) -->
<!-- - First screen the user lands on after setup -->

<!-- The first-run experience should get the user to the core value as fast as possible. Every step before value is friction. -->

<!-- For cross-platform products, describe per-platform first-run paths (e.g., iOS: App Store → first launch → permissions; Web: landing page → sign up → email verification → first use). Note differences in platform onboarding conventions. -->

## Progressive Disclosure

<!-- How complexity is revealed over time: -->
<!-- - What features are visible immediately vs. discovered later? -->
<!-- - How are advanced features surfaced (contextual hints, settings, usage milestones)? -->
<!-- - Is anything hidden until the user demonstrates readiness? -->

<!-- For simple products, this section may be "All features are visible from the start — no progressive disclosure needed." State that explicitly. -->

## Empty States

<!-- What the user sees before they have data. For each screen with an empty state: -->
<!-- - Screen name -->
<!-- - Empty state message (specific text, not "something helpful") -->
<!-- - Call to action (what the user should do to populate this screen) -->
<!-- - Visual treatment (illustration, icon, or plain text) -->

<!-- Empty states are the product's first impression. "No data" is not an empty state design. -->

## Permission Requests

<!-- For each system permission the product requires: -->
<!-- - Permission name (notifications, camera, location, storage, etc.) -->
<!-- - When it's requested (at first launch, at first use of feature, or just-in-time) -->
<!-- - Why the user should grant it (user-facing explanation) -->
<!-- - What happens when denied (degraded experience, feature disabled, or no impact) -->
<!-- - Whether the product re-prompts (and when) -->

<!-- If no permissions are needed, state that explicitly: "No system permissions required." -->

## Tutorial Approach

<!-- How the product teaches its features: -->
<!-- - Approach: tooltips, coach marks, walkthrough, contextual hints, or none -->
<!-- - Which features get tutorial treatment (only non-obvious ones) -->
<!-- - Skippability (user can always skip or dismiss) -->
<!-- - Repeat access (user can re-view tutorial from settings/help) -->

<!-- For a simple utility: "No tutorial needed — interface is self-explanatory" is valid. The test: would a new user of the target persona be confused without guidance? -->

## Return-User Experience

<!-- What happens when a returning user opens the product: -->
<!-- - State restoration (does the product remember where the user left off?) -->
<!-- - What's changed indicators (new data, unread items, updated content) -->
<!-- - Re-engagement for lapsed users (if applicable) -->

<!-- For most products, this is simply "return to the last-viewed screen with current data." Don't over-design re-engagement for a personal utility. -->
