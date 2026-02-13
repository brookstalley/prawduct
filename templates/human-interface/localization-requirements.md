---
artifact: localization-requirements
version: 1
depends_on:
  - artifact: information-architecture
  - artifact: product-brief
depended_on_by:
  - artifact: test-specifications
last_validated: null
---

# Localization Requirements

<!-- This artifact defines the product's internationalization and localization strategy. "English only" is valid but must be explicit — the Builder must know whether to externalize strings. -->

<!-- For a low-risk utility, a quarter page is sufficient. The minimum viable spec is: target locale(s), whether strings are externalized, and date/number formatting approach. -->

## Target Locales

<!-- Which languages and regions the product supports: -->
<!-- - Primary locale (e.g., en-US) -->
<!-- - Additional locales (if any) -->
<!-- - Whether localization is planned for later (affects string externalization decisions now) -->

<!-- "English only, no localization planned" is a valid answer. State it explicitly so the Builder doesn't externalize strings unnecessarily. If localization is planned for later, externalize strings now even if only one locale ships in v1. -->

## String Externalization

<!-- How user-facing text is managed: -->
<!-- - Are strings externalized (in a resource file / i18n library) or inline? -->
<!-- - String file format (JSON, .strings, .arb, etc.) -->
<!-- - Key naming convention (e.g., "screen.element.action") -->
<!-- - How to handle strings with variables (interpolation format) -->

## RTL Support

<!-- Right-to-left language support: -->
<!-- - Is RTL layout required? -->
<!-- - If yes: mirrored layouts, text alignment, directional icons -->
<!-- - If no: state explicitly (e.g., "No RTL locales planned") -->

## Date/Time/Number Formatting

<!-- How locale-sensitive values are displayed: -->
<!-- - Date format (locale-aware or fixed) -->
<!-- - Time format (12h vs. 24h — locale-aware or user preference) -->
<!-- - Number format (decimal separator, thousands separator) -->
<!-- - Currency format (if applicable) -->

## Locale-Specific Adjustments

<!-- Content that changes by locale beyond translation: -->
<!-- - Text expansion (German text is ~30% longer than English — does layout accommodate?) -->
<!-- - Cultural considerations (icons, colors, or imagery with locale-specific meaning) -->
<!-- - Legal or regulatory differences by region (if applicable) -->

## Pluralization

<!-- How plural forms are handled: -->
<!-- - Pluralization strategy (ICU MessageFormat, platform plurals, manual) -->
<!-- - Languages with complex plural rules (if supporting locales beyond English) -->
<!-- - "1 item" vs. "2 items" handling -->
