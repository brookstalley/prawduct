---
artifact: design-direction
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: onboarding-spec
  - artifact: accessibility-spec
last_validated: null
---

# Design Direction

<!-- This artifact defines the visual and interaction identity of the product. It must be concrete enough that the Builder doesn't make aesthetic choices — specific colors, fonts, spacing, not "clean and modern." -->

<!-- Modality note: For games, Visual Identity covers art style (pixel art, vector, 3D, retro). Component Patterns covers game-specific elements (sprites, HUD elements, particle effects, score displays) instead of form widgets and buttons. For dashboards, Component Patterns covers data visualization widgets and density levels. -->

<!-- For a low-risk utility, half a page is sufficient. Specify enough to prevent the Builder from guessing; don't design a brand system. -->

## Visual Identity

<!-- The product's overall visual character: -->
<!-- - Style reference (minimal, playful, professional, retro, etc.) -->
<!-- - Mood / personality (what feeling should the interface convey?) -->
<!-- - Any constraints (must match existing brand, must work in dark environments, etc.) -->

<!-- Be specific: "Friendly and approachable with rounded corners and warm colors" is better than "modern." -->

## Color

<!-- Concrete color values: -->
<!-- - Primary color (hex value) — used for main actions and branding -->
<!-- - Secondary color (hex value) — used for accents and secondary elements -->
<!-- - Background color (hex value) -->
<!-- - Text color (hex value) -->
<!-- - Error/warning/success colors (hex values) -->
<!-- - Dark mode palette (if applicable) -->

<!-- These must be specific hex values, not descriptions like "a nice blue." -->

## Typography

<!-- Font choices: -->
<!-- - Primary font family (for body text) -->
<!-- - Secondary font family (for headings, if different) -->
<!-- - Font sizes: heading, subheading, body, caption (specific values) -->
<!-- - Font weights used (regular, medium, bold) -->

<!-- For mobile: ensure sizes are legible on small screens. For cross-platform: specify system font fallbacks. -->

## Spacing & Layout

<!-- Spacing system: -->
<!-- - Base spacing unit (e.g., 8px grid) -->
<!-- - Standard margins and padding -->
<!-- - Content width constraints (max-width, responsive breakpoints if applicable) -->
<!-- - Touch target minimum size (e.g., 44x44pt for iOS) -->

## Component Patterns

<!-- Reusable interface patterns used across screens: -->
<!-- - Buttons (primary, secondary, destructive — appearance and states) -->
<!-- - Input fields (appearance, focus state, error state) -->
<!-- - Cards/list items (if applicable) -->
<!-- - Navigation elements (tab bar, header bar, etc.) -->
<!-- - Feedback patterns (toasts, alerts, confirmations) -->

<!-- For cross-platform products, specify shared design tokens (colors, typography, spacing) first, then per-platform component patterns (iOS native vs. web custom vs. Android Material). -->

## Motion & Transitions

<!-- How the interface moves: -->
<!-- - Screen transitions (slide, fade, none) -->
<!-- - Interactive feedback (button press, loading, success/error) -->
<!-- - Animation duration guidelines (e.g., 200-300ms for transitions) -->
<!-- - Reduced motion behavior (what changes when user prefers reduced motion) -->

<!-- For a low-risk utility, "platform default transitions, no custom animations" is acceptable. -->

## Platform Conventions

<!-- Platform-specific design considerations: -->
<!-- - Which platform conventions to follow (iOS HIG, Material Design, web conventions) -->
<!-- - Where the product intentionally deviates from platform norms (with rationale) -->
<!-- - Platform-specific interaction patterns (swipe-to-delete, pull-to-refresh, etc.) -->
