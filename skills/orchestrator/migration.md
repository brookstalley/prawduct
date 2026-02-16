# Migration Mode — Old prawduct Schema Migration

Migration Mode converts project-state.yaml files from older prawduct schema versions to the current format (v2). The Orchestrator routes here when `prawduct-init.sh` reports `next_action: "migration"` and the `schema_version_raw` field identifies the source version.

## When This File Is Read

The Orchestrator routes here from SKILL.md Step 1c when the project has a `project-state.yaml` with a detected old schema version. The `prawduct-init.sh` output provides:
- `schema_version_raw`: the raw detected version string ("v0", "v0.5", "v1", "current")
- `content_state`: current content analysis including `has_classification`, `has_product_definition`
- `existing_docs`: classified documentation inventory

---

## Migration Tiers

### Tier 1: v1 → v2 (Lightweight)

**When:** `schema_version_raw` is "v1" (has top-level `structural:` key, no `schema_version` field)

**Approach:** Mechanical field additions + LLM validation. Minimal content changes — the v1 format is structurally close to v2.

**Steps:**

1. **Read the existing file** completely. Preserve all user content.

2. **Add missing fields:**
   - Add `schema_version: 2` at the top of the file
   - Wrap existing `structural:` block inside `classification:` if not already nested:
     ```yaml
     classification:
       structural:
         # ... existing structural content
     ```
   - Add `domain_characteristics: []` under `classification:` if absent
   - Add `risk_profile:` skeleton under `classification:` if absent:
     ```yaml
     risk_profile:
       overall: null  # To be assessed
       factors: []
     ```

3. **Derive `domain_characteristics`** from existing content:
   - Read `product_definition.vision`, existing docs, and structural characteristics
   - Generate 1-3 domain-specific characteristics with implications
   - Mark as `"# Inferred during v1→v2 migration — verify with product owner"`

4. **Validate coherence:**
   - Check that `structural` values match what the codebase shows
   - Verify `product_definition` fields are still accurate
   - Flag any inconsistencies for user review

5. **Present migration summary to user:**
   > "I've migrated your project-state.yaml from v1 to v2. Changes:
   > - Added `schema_version: 2`
   > - Nested structural characteristics under `classification:`
   > - Derived [N] domain characteristics from your product description
   > - [Any inconsistencies found]
   >
   > The migration preserves all your existing content. Review the new `domain_characteristics` section — I inferred those from your product description."

6. **Write the updated file** to `.prawduct/project-state.yaml`.

---

### Tier 2: v0.5 → v2 (Moderate)

**When:** `schema_version_raw` is "v0.5" (has top-level `concerns:` key)

**Approach:** Field mapping via correspondence table + LLM re-derivation of missing sections. User confirmation required.

**Correspondence table:**
| v0.5 `concerns.*` | v2 `classification.structural.*` |
|---|---|
| `human_interface` | `has_human_interface` (add `modality` and `platform` from codebase) |
| `unattended_operation` | `runs_unattended` (add `trigger` from codebase) |
| `api_surface` | `exposes_programmatic_interface` (add `consumers` from codebase) |
| `multi_party` | `has_multiple_party_types` |
| `data_sensitivity` / `sensitive_data` | `handles_sensitive_data` |
| `constrained_environment` | (dropped — not a v2 structural characteristic) |
| `external_integrations` | (dropped — covered by domain_characteristics) |

**Steps:**

1. **Read the existing file** completely. Preserve all user content.

2. **Map structural characteristics** using the correspondence table above.
   - For each v0.5 concern that maps to a v2 structural characteristic, carry over the value
   - For concerns that map to `null` in v2, note them as candidates for `domain_characteristics`

3. **Re-derive missing sections:**
   - `classification.domain` — infer from product description and existing docs
   - `classification.domain_characteristics` — derive from dropped concerns + product description
   - `classification.risk_profile` — assess from structural characteristics and product context

4. **Preserve user content:** Copy verbatim all sections that exist in both v0.5 and v2:
   - `product_definition`, `technical_decisions`, `design_decisions`
   - `build_plan`, `build_state`, `iteration_state`
   - `change_log`, `observation_backlog`

5. **Present migration summary to user** showing:
   - What was mapped (concern → structural characteristic)
   - What was dropped (concerns with no v2 equivalent)
   - What was newly derived (domain, domain_characteristics, risk_profile)
   - Any content that couldn't be preserved

6. **Wait for user confirmation** — this is a genuine blocking question. The concern→structural mapping involves interpretation.

7. **Write the v2 file** to `.prawduct/project-state.yaml`. Add a change_log entry documenting the migration.

---

### Tier 3: v0 → v2 (Heavy — Re-analysis)

**When:** `schema_version_raw` is "v0" (has top-level `product_shape:` or `shape:` key)

**Approach:** Extract user content, re-run structural detection on the codebase, use preserved text as a head start for artifact generation. This is essentially onboarding with preserved context.

**Steps:**

1. **Extract user content** from the v0 file:
   - Product description / vision text
   - Any decisions or rationale recorded
   - Build plan content (if any)
   - Technical choices documented

2. **Preserve extracted content** in a temporary working note: `.prawduct/working-notes/v0-migration-preserved-content.md`

3. **Re-run structural detection:**
   - If the `existing_docs` from prawduct-init show architecture docs or API specs, read them
   - Analyze the codebase using the same approach as Onboarding Mode Phase 1 (read `skills/orchestrator/onboarding.md`)
   - Use the preserved v0 content to seed product understanding rather than starting from scratch

4. **Present migration summary to user:**
   > "Your project uses an old prawduct format (v0) that's too different to mechanically migrate. I'll re-analyze your codebase to generate current-format artifacts, using the content from your existing project-state.yaml as a starting point.
   >
   > **Preserved from v0:** [list what was extracted]
   > **Will re-derive:** classification, structural characteristics, domain characteristics, risk profile
   >
   > This is similar to fresh onboarding but faster because I have your existing product description and decisions."

5. **Wait for user confirmation** — genuine blocking question.

6. **Proceed with Onboarding Mode** (read `skills/orchestrator/onboarding.md`), passing the preserved content as pre-existing knowledge. Skip analysis steps where the preserved content provides sufficient information.

---

## After Migration

Regardless of tier:

1. Add a `change_log` entry documenting the migration:
   ```yaml
   - what: "Migrated project-state.yaml from [version] to v2"
     why: "Old schema format detected; migrated to current format for full framework governance"
     blast_radius: ".prawduct/project-state.yaml"
     classification: process
     date: <today>
   ```

2. Set `current_stage` appropriately:
   - If the project was previously in a build stage → `iteration`
   - If the project had no build progress → `definition` (to resume where they left off)

3. Return control to the Orchestrator for Session Resumption. The project now has a v2 project-state.yaml and can use full framework governance.

---

## Edge Cases

**Mixed content:** If the old file has some v2-compatible sections alongside old-format sections, preserve the v2 sections and only migrate the old ones.

**Corrupt files:** If the file can't be parsed at all, treat as v0 (extract what's readable, re-derive the rest).

**Framework repo:** Migration is never triggered for the framework repo (`self_hosted` scenario). The framework's own project-state.yaml is always maintained at the current schema.
