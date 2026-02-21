# Design Proposal: Design System Integration

**Status**: Proposal (not yet implemented)
**Tier**: 3 (Working Note — design exploration)
**Created**: 2026-02-21
**Expires**: 2026-03-07

---

## Problem Statement

Products with user interfaces get visual design guidance via `design-direction.md`, which specifies colors, typography, spacing, and component patterns. But this is **art direction**, not a **design system**. The difference matters:

- **Art direction** (what we have): "Use blue (#3B82F6) for primary actions, 8px grid spacing, Inter font." This tells the Builder what aesthetic choices to make.
- **Design system** (what we need): "Primary action color is `color.action.primary` (value: #3B82F6). All interactive elements reference this token. If the brand changes, update the token value; all components follow automatically."

### Why This Matters

The art direction approach breaks down as products grow:

1. **Magic values proliferate.** Is this blue `#3B82F6` or `#2563EB`? Without named tokens, the Builder makes per-instance color decisions that drift from the intended palette.
2. **Component consistency is manual.** Every screen reimplements button styles from the description in design-direction.md. Inconsistencies accumulate.
3. **Theme changes require find-and-replace.** Dark mode, high contrast, and brand refreshes become error-prone bulk operations.
4. **Cross-platform products have no shared vocabulary.** iOS and web implementations use the same colors but express them differently with no shared source of truth.
5. **The Critic can't verify design consistency** because there's no machine-readable specification to check against. The Critic can read "primary color: #3B82F6" in design-direction.md but can't mechanically verify that every button in the codebase uses that value.

### What Exists Today

`templates/human-interface/design-direction.md` covers:
- Visual Identity (style, mood, constraints)
- Color (hex values for primary, secondary, background, text, semantic colors)
- Typography (font families, sizes, weights)
- Spacing & Layout (base unit, margins, breakpoints, touch targets)
- Component Patterns (buttons, inputs, cards, navigation, feedback)
- Motion & Transitions (screen transitions, interactive feedback, reduced motion)
- Platform Conventions (which platform guidelines to follow)

This is good art direction. It establishes visual intent. But it doesn't provide a **structured, referenceable system** that the Builder implements as code infrastructure.

---

## The Standard: W3C Design Tokens

The W3C Design Tokens Community Group has published a draft specification for a platform-agnostic design token format (https://www.designtokens.org/tr/drafts/format/). Design tokens are the smallest unit of a design system — named, typed values that represent design decisions.

### Token Format (W3C Draft)

```json
{
  "color": {
    "$description": "Color palette",
    "action": {
      "primary": { "$value": "#3B82F6", "$type": "color", "$description": "Primary interactive elements" },
      "primary-hover": { "$value": "#2563EB", "$type": "color" },
      "destructive": { "$value": "#EF4444", "$type": "color", "$description": "Destructive actions (delete, remove)" }
    },
    "surface": {
      "background": { "$value": "#FFFFFF", "$type": "color" },
      "background-secondary": { "$value": "#F3F4F6", "$type": "color" },
      "foreground": { "$value": "#111827", "$type": "color", "$description": "Primary text" }
    },
    "feedback": {
      "success": { "$value": "#10B981", "$type": "color" },
      "warning": { "$value": "#F59E0B", "$type": "color" },
      "error": { "$value": "#EF4444", "$type": "color" }
    }
  },
  "spacing": {
    "xs": { "$value": "4px", "$type": "dimension" },
    "sm": { "$value": "8px", "$type": "dimension" },
    "md": { "$value": "16px", "$type": "dimension" },
    "lg": { "$value": "24px", "$type": "dimension" },
    "xl": { "$value": "32px", "$type": "dimension" }
  },
  "typography": {
    "body": {
      "$value": { "fontFamily": "Inter", "fontSize": "16px", "fontWeight": 400, "lineHeight": 1.5 },
      "$type": "typography"
    },
    "heading": {
      "$value": { "fontFamily": "Inter", "fontSize": "24px", "fontWeight": 600, "lineHeight": 1.2 },
      "$type": "typography"
    }
  },
  "borderRadius": {
    "sm": { "$value": "4px", "$type": "dimension" },
    "md": { "$value": "8px", "$type": "dimension" },
    "full": { "$value": "9999px", "$type": "dimension" }
  }
}
```

### Why This Format

- **Platform-agnostic**: Tokens transform into CSS custom properties, Swift asset catalogs, Kotlin resources, Tailwind config — one source of truth, multiple consumers.
- **Machine-readable**: The Critic can parse tokens and verify UI code references them (no magic values).
- **Compositional**: Tokens reference other tokens via aliases (`{color.action.primary}`), enabling theme variants.
- **Standardizing**: The W3C draft is converging toward a stable format; early adoption positions products for tooling compatibility.

---

## Proposed Solution

### A. Two-Document Architecture: Direction + System

**`design-direction.md`** (existing, evolved): Keeps its current role as the **intent** document — visual identity, mood, style references, platform conventions. This is "what we want it to feel like." It's the input to the design system.

**`design-system.md`** (new): The **implementation** document — design tokens in W3C format, component inventory, usage rules, theme support. This is "how we express the design intent in code."

**Dependency**: `design-system.md` depends on `design-direction.md`. Token values derive from direction choices. If direction changes, tokens update.

```
Product Brief
    │
    ├──► Design Direction (intent, mood, aesthetic choices)
    │         │
    │         ▼
    │    Design System (tokens, components, usage rules)
    │         │
    │         ▼
    │    Screen Specs (reference design system tokens + components)
    │
    ├──► Accessibility Spec (references design system for contrast, sizing)
```

### B. Template Structure: design-system.md

```markdown
---
artifact: design-system
version: 1
depends_on:
  - artifact: design-direction
depended_on_by:
  - artifact: screen-spec
  - artifact: accessibility-spec
  - artifact: onboarding-spec
last_validated: null
---

# Design System

<!-- STATUS: This is a design specification, not generated code. The Builder
     implements this specification as code infrastructure (CSS custom properties,
     theme provider, etc.) in the scaffold chunk. -->

## Design Tokens

<!-- Tokens in W3C Design Tokens format. These are the single source of truth
     for all visual values in the product. No raw color/spacing/typography values
     should appear in UI code — everything references a token.

     Proportionality:
     - Low-risk utility: 5-15 tokens (primary colors, one font, base spacing)
     - Medium-risk app: 20-40 tokens (full palette, type scale, spacing scale, radii)
     - High-risk / brand-critical: 40+ tokens with theme variants (light/dark/high-contrast)
-->

### Color Tokens
<!-- Semantic color names, not raw values. Organized by role:
     - action: interactive element colors (primary, secondary, destructive)
     - surface: background and container colors
     - content: text and icon colors
     - feedback: success, warning, error, info
     - border: divider and outline colors
-->

### Spacing Tokens
<!-- Scale based on the base unit from design-direction.md.
     Typically: xs, sm, md, lg, xl, 2xl
     The scale should feel consistent — each step is visibly distinct. -->

### Typography Tokens
<!-- Composite tokens: fontFamily + fontSize + fontWeight + lineHeight.
     Named by role: heading-1, heading-2, body, body-small, caption, label
     Must include the font stack (with system fallbacks). -->

### Shape Tokens
<!-- Border radii, shadows, borders.
     Named by role or size: radius-sm, radius-md, radius-full
     Shadow tokens for elevation levels if applicable. -->

### Motion Tokens
<!-- Duration and easing values.
     Named by use: transition-fast, transition-normal, transition-slow
     Easing: ease-default, ease-in, ease-out
     These tokens are optional for low-risk products. -->

## Component Patterns

<!-- Reusable UI patterns built from tokens. Each pattern specifies:
     - Which tokens it uses
     - States (default, hover, active, disabled, focus, error)
     - Variants (primary, secondary, ghost, destructive)
     - Accessibility requirements (focus ring, ARIA, touch target)

     Proportionality:
     - Low-risk: 3-5 patterns (button, input, card — whatever the product needs)
     - Medium-risk: 8-15 patterns (full form kit, navigation, feedback, layout)
     - High-risk: Complete component inventory with documented variants

     Do NOT enumerate every possible component. Document patterns the product
     actually uses, identified from screen specs and core flows. -->

## Theme Support

<!-- If the product supports multiple themes (light/dark, brand variants):
     - How themes override token values (token aliases vs. separate token files)
     - Default theme
     - Theme switching mechanism
     - Which tokens change between themes and which are fixed

     For low-risk products: "Single theme. No theme switching needed." is valid. -->

## Platform Implementation

<!-- How tokens are consumed in the product's platform:
     - Web: CSS custom properties generated from tokens
     - React Native: theme provider with token values
     - iOS native: asset catalog + Swift constants
     - Cross-platform: shared token file → per-platform build step

     Include the token-to-platform mapping so the Builder knows exactly how to
     implement the token system. -->

## Usage Rules

<!-- Rules for maintaining design system consistency:
     - No raw values in UI code (all visual properties reference tokens)
     - New components must use existing tokens (not introduce new values)
     - When a new token is needed, add it here first, then reference it
     - Token naming convention: category.role.variant (e.g., color.action.primary)
-->
```

### C. Proportionality

Not every product needs a full design system. The Artifact Generator determines depth from risk profile and structural characteristics:

| Context | Design System Depth |
|---------|-------------------|
| Low-risk utility, single screen | Minimal: 5-15 tokens (primary/secondary colors, font, base spacing). Component patterns listed but not formally specified. |
| Medium-risk app, multiple screens | Standard: 20-40 tokens with full color palette, typography scale, spacing scale, border radii. Component patterns documented with states. |
| High-risk / cross-platform / brand-critical | Full: Complete token hierarchy, component inventory with variants, theme support (light/dark/high-contrast), platform-specific implementation guides. |
| CLI / terminal product | Minimal: Color tokens for output formatting (success/error/warning/info, heading, muted). No spacing/typography tokens (terminal controls those). |
| Minimal interface (LEDs, indicators) | None: Design direction covers indicator behavior. Design tokens don't apply to hardware interfaces. |

### D. Discovery Integration

Expand `has_human_interface` amplification in the Domain Analyzer for dimension 10 (Product Identity):

**New amplification questions (Tier 2 — ask if not inferable):**
- "Do you have an existing design system, style guide, or brand guidelines?" (onboarding context)
- "Will this need to support multiple themes (light mode / dark mode, brand variants)?"
- "Are there existing products this should feel visually consistent with?"

**Inference defaults** (when user has no preference):
- Single theme (unless the platform convention is dark mode support)
- No existing design system (generate from design direction)
- Design system depth determined by risk profile

### E. Builder Integration

The Builder implements design tokens as infrastructure in the first UI-related chunk:

1. **Generate token file** from `design-system.md` in the platform-appropriate format
2. **Configure consumption mechanism** (CSS custom properties, theme provider, constants file)
3. **All subsequent UI code** references tokens by name, never raw values
4. **Component implementations** follow the patterns specified in design-system.md

**Builder checkpoint**: Before starting UI chunks, verify token infrastructure is in place. If design-system.md exists and tokens aren't implemented, that's a blocking issue.

### F. Critic Integration

**Check 1 (Spec Compliance)** — add for `has_human_interface` products with design-system.md:
- No magic color/spacing/typography values in UI code (all visual properties trace to a named token)
- Component implementations match the patterns specified in design-system.md
- Token values match design-direction.md choices (colors in tokens = colors in direction)

**Check 5 (Coherence)** — add:
- Design token definitions are consistent with design-direction.md
- Screen specs reference design system components (not ad hoc implementations)
- Cross-platform products share the same token set (platform-specific implementations, shared tokens)

**Severity**: WARNING for magic values (not blocking, but must address before delivery). BLOCKING only if the design system is fundamentally inconsistent with the direction.

### G. Review Lens Integration

**Design Lens** for `has_human_interface`:
- Add structural check: "Is the design system used consistently across screens?"
- Add structural check: "Do new components follow established patterns, or introduce ad hoc variants?"
- Theme support: if design-system.md specifies dark mode, verify it's implemented

**Architecture Lens**:
- Check for token infrastructure: is there a single source of truth for design values?
- Check for build pipeline: are tokens transformed for the platform, or copy-pasted?

### H. Onboarding Integration

For existing codebases being onboarded (`skills/orchestrator/onboarding.md`):

1. **Scan** for existing design patterns:
   - CSS: variables, custom properties, theme files, utility classes
   - JS/TS: styled-components themes, Tailwind config, design constants
   - Mobile: asset catalogs, resource files, theme definitions
2. **Extract** the implicit design system into W3C Design Token format
3. **Present** to user for confirmation: "I found these design patterns in your codebase: [summary]. Here's how they'd look as design tokens: [preview]. Does this capture your design system?"
4. **Generate** design-system.md from confirmed tokens

---

## Integration Points

| File | Change | Scope |
|------|--------|-------|
| `templates/human-interface/design-system.md` | **New** — template for design system artifact | New file |
| `templates/human-interface/design-direction.md` | Add `depended_on_by: design-system` in frontmatter; add cross-reference paragraph | Small edit |
| `skills/domain-analyzer/SKILL.md` | Add design system discovery questions to `has_human_interface` amplification (dimension 10) | Small addition |
| `skills/artifact-generator/SKILL.md` | Add design-system.md to `has_human_interface` artifact set with proportionality rules | Medium addition |
| `skills/builder/SKILL.md` | Add design token implementation guidance (scaffold chunk) | Medium addition |
| `agents/critic/SKILL.md` | Add design token compliance to Check 1, design system coherence to Check 5 | Medium addition |
| `agents/review-lenses/SKILL.md` | Add design system consistency checks to Design Lens, token architecture to Architecture Lens | Small addition |
| `skills/orchestrator/onboarding.md` | Add design pattern extraction to onboarding flow | Medium addition |
| `docs/high-level-design.md` | Update artifact dependency diagram to include design-system.md | Small edit |

**Estimated scope**: Structural-tier DCP. 1 new template, 8 modified files.

---

## Implementation Sequence

1. Create the `design-system.md` template
2. Update `design-direction.md` frontmatter and cross-references
3. Update Domain Analyzer with discovery questions
4. Update Artifact Generator with generation rules
5. Update Builder with token implementation guidance
6. Update Critic with compliance checks
7. Update Review Lenses with design system checks
8. Update onboarding flow
9. Update high-level-design.md dependency diagram
10. Run Critic review

**Dependency**: Should be implemented after the Coverage Audit Mechanism (so the new concern can be registered in the registry). Independent of the Observability Strategy proposal.

---

## Open Questions

1. **Template vs. in-artifact tokens**: Should design tokens be in the artifact markdown (for human readability + Critic access) or in a separate `.tokens.json` file (for machine readability + tool compatibility)? Proposed answer: **both** — the artifact contains the canonical tokens in a code block, and the Builder generates the platform-specific files from it. The markdown is the source of truth.

2. **Existing design-direction.md content overlap**: The current design-direction.md has Color, Typography, Spacing sections with specific values — the same information that would be in design tokens. Should these sections be removed from design-direction.md (moving specifics to design-system.md) or kept as the "intent" version? Proposed answer: **keep in design-direction.md as intent, duplicate as tokens in design-system.md**. The direction says "use Inter at 16px for body text" (a design decision); the system says `typography.body: { fontFamily: "Inter", fontSize: "16px" }` (an implementation specification). The Critic's coherence check verifies they match.

3. **Token tooling**: Should the framework recommend specific design token tooling (Style Dictionary, Token Studio, etc.)? Proposed answer: **no** — consistent with Generality Over Enumeration. The framework specifies the W3C format as the standard; tool selection is a technology decision documented in the dependency manifest.
