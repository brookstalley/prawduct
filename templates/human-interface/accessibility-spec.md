---
artifact: accessibility-spec
version: 1
depends_on:
  - artifact: screen-spec
  - artifact: design-direction
  - artifact: nonfunctional-requirements
last_validated: null
---

# Accessibility Specification

<!-- This artifact defines the product's accessibility requirements. Requirements must be testable — "accessible" is not a requirement, "4.5:1 contrast ratio for body text" is. -->

<!-- Modality note: For games, supplement WCAG with game accessibility guidance: difficulty options, control remapping, colorblind modes, subtitle options for audio cues, seizure warnings for flashing content. "Keyboard navigation" covers game controls (remappable inputs, alternative control schemes), not form tabbing. For creative tools, consider motor accessibility (precision requirements, alternative input methods). -->

<!-- For a low-risk utility, half a page is sufficient. Specify the compliance target and key requirements; don't write a full WCAG audit plan. -->

## Target Compliance Level

<!-- What accessibility standard the product targets: -->
<!-- - WCAG 2.1 Level AA (recommended minimum for most products) -->
<!-- - WCAG 2.1 Level A (acceptable for low-risk, personal-use products) -->
<!-- - Platform-specific guidelines (iOS Accessibility, Android Accessibility) -->
<!-- - Game-specific guidelines (Game Accessibility Guidelines, Xbox Accessibility Guidelines) -->

<!-- "Best effort" is acceptable for a personal utility but must be explicit. -->

## Keyboard Navigation

<!-- How the product works without a pointer/touch: -->
<!-- - Tab order for interactive elements -->
<!-- - Keyboard shortcuts (if any) -->
<!-- - Focus indicators (visible focus ring or equivalent) -->
<!-- - Trap prevention (user can always tab out of any component) -->

## Screen Reader Support

<!-- How the product works with assistive technology: -->
<!-- - Semantic structure (headings, landmarks, lists) -->
<!-- - Labels for interactive elements (buttons, inputs, links) -->
<!-- - Alt text for images and icons -->
<!-- - Dynamic content announcements (live regions for updates) -->
<!-- - Custom component accessibility (ARIA roles if applicable) -->

## Color & Contrast

<!-- Visual accessibility requirements: -->
<!-- - Minimum contrast ratio for text (4.5:1 for body, 3:1 for large text per WCAG AA) -->
<!-- - Color is not the only indicator of state (error states use icon + text, not just red) -->
<!-- - Colorblind-safe palette verification -->

## Focus Management

<!-- How focus moves through the interface: -->
<!-- - Initial focus on page/screen load -->
<!-- - Focus after modal dialogs open and close -->
<!-- - Focus after dynamic content changes (new items added, items removed) -->
<!-- - Focus restoration after navigation (back button returns focus to trigger) -->

## Touch Targets

<!-- For touch interfaces: -->
<!-- - Minimum touch target size (44x44pt recommended for iOS, 48x48dp for Android) -->
<!-- - Spacing between touch targets -->
<!-- - Gesture alternatives (swipe actions have button equivalents) -->

## Reduced Motion

<!-- For users who prefer reduced motion: -->
<!-- - Which animations are removed or simplified -->
<!-- - How transitions change (cross-fade vs. slide, or instant) -->
<!-- - How to detect preference (prefers-reduced-motion media query or platform setting) -->

## Platform-Specific Guidance

<!-- Platform accessibility features to support: -->
<!-- - iOS: Dynamic Type, VoiceOver, Switch Control, Reduce Motion -->
<!-- - Android: TalkBack, font scaling, color inversion -->
<!-- - Web: screen readers, keyboard navigation, high contrast mode -->
<!-- Only include platforms relevant to this product. -->
