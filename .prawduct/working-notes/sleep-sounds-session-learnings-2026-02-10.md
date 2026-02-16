# Session Learnings: Sleep Sounds App (2026-02-10)

Created: 2026-02-10
Source: Live product session — iOS sleep sounds app with generative audio/visuals

## Changes Made

### 1. Domain Analyzer — Tier 1 Q2: "Core action" → "Core experience"
**Observation:** The original question asked "What's the verb?" — implying the user is the active agent. The sleep app's core experience is passive: the system generates ambient audio and visuals, the user receives them. This active-voice bias would miss the entire interaction model for recommendation engines, ambient tools, generative art, smart home automation, feed curation, etc.

**Fix:** Reframed as "core experience" that explicitly covers both active-user and system-driven products. Added note that the answer shapes downstream decisions: active products need selection/control UI; system-driven products need feedback/learning mechanisms.

**Generality test:** Family utility (active) — still works. B2B API (system processes) — better framing. Data pipeline (automated) — better framing. Recommendation engine (system generates) — now covered. Ambient experience (passive) — now covered.

### 2. Domain Analyzer — Tier 1 Q3: Added physical context alongside platform
**Observation:** "Where do people use this?" focused only on device. The sleep app's dark-room constraint drove major design decisions (brightness caps, fade behaviors, dark launch screen). Physical context is equally impactful for many products: cooking app (wet hands), navigation (bright sunlight, glancing), exercise tracker (rain, motion), conference app (crowded room, quick glances).

**Fix:** Expanded the question to include physical conditions — not just device but environment. Added examples of how context drives constraints.

**Generality test:** Applies across all product types with a user-facing surface.

### 3. Orchestrator — Risk re-evaluation after discovery
**Observation:** Initial classification rated technical complexity as "low" based on the user's description ("makes soothing sounds"). Discovery revealed generative audio synthesis with evolving filters and GPU-rendered ambient visuals — medium complexity. The framework had no mechanism to catch this drift.

**Fix:** Added a step between discovery and definition to re-evaluate risk factors. Includes guidance: don't restart discovery just because risk increased, but check for gaps.

**Generality test:** Any product where the initial description understates technical depth. Common for non-technical users describing technically ambitious products.

## Observations NOT Acted On (and why)

### "Share" ambiguity
User said "share with friends" — could mean App Store distribution or in-app content sharing. These have very different architectural implications (no backend vs. backend needed). Considered adding a proactive expertise item about probing sharing ambiguity.

**Decided against:** Tier 2 Q5 already asks about multi-user data sharing. The distribution-vs-content distinction is a specific instance of a more general pattern: trace user-mentioned capabilities to their architectural implications. The existing proactive expertise instruction ("follow each entity to its implications") covers this pattern generally. One session doesn't justify a new enumerated concern (Learn Slowly principle).

**Watch for:** If this ambiguity recurs in future sessions, consider strengthening the general principle about tracing capabilities to architecture.

### Health/wellness domain overlay
The app spans health and entertainment domains. No health-specific domain overlay exists.

**Decided against:** The useful insights from this session (passive experience, physical context) are general, not health-specific. A health overlay might add questions about medical claims, FDA considerations, or HIPAA — but this app triggers none of those. Adding a health overlay based on one non-medical wellness app would over-fit.

**Watch for:** A session with a product involving actual health data (symptoms, medications, vitals) would justify a health overlay focused on medical-grade concerns.

### Generative/procedural content as a formal pattern
The app's core is procedural audio and procedural visuals — the data model needed to capture "parameter spaces" rather than CRUD entities. Considered adding guidance about generative/parametric data models.

**Decided against:** The existing data model guidance ("follow each entity to its implications") handled this naturally once the entities were identified. The artifact generator produced appropriate parametric entities without special instructions. This is the framework working as intended — general principles adapting to specific products.

### Dark room / ambient experience design guidance
Considered adding Design Lens considerations for ambient/sensory products (brightness limits, fade behaviors, audio fade-in to prevent startle).

**Decided against:** Too specific to one product type. The strengthened Platform question (physical context) should naturally surface these constraints during discovery. The Design Lens already checks for loading states and state transitions, which covers fade behavior. Adding ambient-specific guidance would be enumeration, not generalization.

## Other Notes

- The user showed good product instincts (intermediate product thinking, intermediate design sensibility) despite basic technical depth. The "random play + thumbs up/down" interaction model was proposed by the user unprompted — a strong UX instinct.
- Zero third-party dependencies. All Apple-native frameworks. This is a clean architecture that the framework correctly surfaced through proportionate technical decisions.
- The "zero-decision bedtime" philosophy was the user's core design insight. The framework captured it as a success criterion ("app requires zero decisions at bedtime") and as a scope boundary ("complex settings UI" in the never list). This pattern — minimal interaction at point of use, deferred feedback — is worth recognizing if it recurs.
- Session generated 7 artifacts, 24 test scenarios, 0 blocking review findings, 2 warnings, 3 notes. Proportionality calibration seems correct for a low-risk product.
