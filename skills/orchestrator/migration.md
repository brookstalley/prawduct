# Migration Mode — Old prawduct Schema and Layout Migration

Migration Mode converts projects from older prawduct versions to the current format. It handles both **layout migration** (files at project root instead of `.prawduct/`) and **schema migration** (old field names and structure). The Orchestrator routes here when `prawduct-init.sh` reports `next_action: "migration"` with any `schema_version_raw` or `scenario` starting with `"migration"`.

## When This File Is Read

The Orchestrator routes here from SKILL.md Step 1c when:
- `scenario: "migration_v0"` / `"migration_v1"` — old schema version detected
- `schema_version_raw: "v0.5"` — v0.5-specific field names detected (top-level or nested)
- `scenario: "migration_layout"` — project-state.yaml and/or artifacts at root instead of `.prawduct/`

The `prawduct-init.sh` output provides:
- `schema_version_raw`: detected version string ("v0", "v0.5", "v1", "current")
- `root_level_files`: dict of prawduct outputs found at project root
- `content_state`: current content analysis including `has_classification`, `has_product_definition`, `artifacts_location`
- `existing_docs`: classified documentation inventory

---

## Unified Migration Flow

Every migration runs through these phases in order. Each phase checks whether it applies and skips if not needed.

### Phase A: Layout Migration

**When:** `root_level_files` from prawduct-init shows any files at root (`project_state`, `artifacts_dir`, `observations_dir`, or `working_notes_dir` is true).

**Purpose:** Move prawduct outputs from project root into `.prawduct/` where they belong.

**Steps:**

1. **Inventory root-level prawduct files.** Check for:
   - `project-state.yaml` at root
   - `artifacts/` directory at root
   - `framework-observations/` directory at root
   - `working-notes/` directory at root

2. **For each file/directory that exists at root AND doesn't exist in `.prawduct/`:**
   - Use `git mv` if in a git repo, otherwise `mv`
   - `project-state.yaml` → `.prawduct/project-state.yaml`
   - `artifacts/` → `.prawduct/artifacts/`
   - `framework-observations/` → `.prawduct/framework-observations/`
   - `working-notes/` → `.prawduct/working-notes/`

3. **Handle conflicts** (file/directory exists at BOTH locations):
   - Keep the `.prawduct/` version (it's newer)
   - Preserve root version as `.prawduct/working-notes/pre-migration-root-{name}.yaml` (for project-state.yaml) or note the conflict for the user
   - For directories that exist in both locations, merge contents — move files from root that don't exist in `.prawduct/`, skip duplicates

4. **Verify** all files accessible at new locations.

5. **Clean up empty directories** left at root after relocation (e.g., `artifacts/`, `framework-observations/`, `working-notes/`). Use `rmdir` (safe — only removes if empty).

**Skip this phase** if no `root_level_files` are true.

---

### Phase B: Schema Migration

**When:** `schema_version_raw` is not "v2", "current", or null. Operates on `.prawduct/project-state.yaml` (post-relocation from Phase A).

Apply the appropriate tier based on the detected version:

#### Tier 1: v1 → v2 (Lightweight)

**When:** `schema_version_raw` is "v1" (has top-level `structural:` key, no `schema_version` field)

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
   - Mark as `"# Inferred during v1->v2 migration -- verify with product owner"`

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
   > The migration preserves all your existing content. Review the new `domain_characteristics` section."

6. **Write the updated file** to `.prawduct/project-state.yaml`.

#### Tier 2: v0.5 → v2 (Moderate)

**When:** `schema_version_raw` is "v0.5" (has `concerns:` key — top-level or nested — or v0.5-specific field names like `api_surface`, `constrained_environment`, `external_integrations` at any indent level)

**Correspondence table** (search for these field names at any indent level, not just under top-level `concerns:`):

| v0.5 field | v2 `classification.structural.*` |
|---|---|
| `human_interface` | `has_human_interface` (add `modality` and `platform` from codebase) |
| `unattended_operation` | `runs_unattended` (add `trigger` from codebase) |
| `api_surface` | `exposes_programmatic_interface` (add `consumers` from codebase) |
| `multi_party` | `has_multiple_party_types` |
| `data_sensitivity` / `sensitive_data` | `handles_sensitive_data` |
| `constrained_environment` | (dropped -- not a v2 structural characteristic) |
| `external_integrations` | (dropped -- covered by domain_characteristics) |

**Steps:**

1. **Read the existing file** completely. Preserve all user content.

2. **Map structural characteristics** using the correspondence table above.
   - Search for v0.5 field names at any indent level (not just under a top-level `concerns:` key)
   - For each v0.5 field that maps to a v2 structural characteristic, carry over the value
   - For fields that map to `null` in v2, note them as candidates for `domain_characteristics`

3. **Re-derive missing sections:**
   - `classification.domain` — infer from product description and existing docs
   - `classification.domain_characteristics` — derive from dropped concerns + product description
   - `classification.risk_profile` — assess from structural characteristics and product context

4. **Preserve user content:** Copy verbatim all sections that exist in both v0.5 and v2:
   - `product_definition`, `technical_decisions`, `design_decisions`
   - `build_plan`, `build_state`, `iteration_state`
   - `change_log`, `observation_backlog`
   - Any non-standard project-specific sections (e.g., `conventions:`, custom metadata). Preserve verbatim — these are user content.

5. **Present migration summary to user** showing:
   - What was mapped (concern -> structural characteristic)
   - What was dropped (concerns with no v2 equivalent)
   - What was newly derived (domain, domain_characteristics, risk_profile)
   - Any content that couldn't be preserved

6. **Wait for user confirmation** — this is a genuine blocking question. The concern->structural mapping involves interpretation.

7. **Write the v2 file** to `.prawduct/project-state.yaml`.

#### Tier 3: v0 → v2 (Heavy — Re-analysis)

**When:** `schema_version_raw` is "v0" (has top-level `product_shape:` or `shape:` key)

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

### Phase C: V2 Scaffolding

**When:** Always runs after Phase B (or if Phase B was skipped because the schema was already current). Ensures ALL v2 sections exist.

**Steps:**

1. **Read `.prawduct/project-state.yaml`** (the post-migration version).

2. **Add missing top-level sections** with empty/default values (only add if absent):
   ```yaml
   schema_version: 2
   observation_backlog:
     last_triage: null
     items: []
   deprecated_terms: []
   ```

3. **Check `artifact_manifest` structure:**
   - **Split file pointers:** If `definition_file`, `artifact_manifest_file`, or `deferred_backlog_file` pointers exist, those sections live in separate files. Do not overwrite pointers with inline content — the split format is valid and preferred for large projects.
   - **Product repos:** Only the `artifacts` category is needed. All entries should have `file_path` in `.prawduct/artifacts/`. The 5-category structure (`source_components`, `tooling`, `test_specs`, `human_docs`) applies only to the framework repo.
   - **Framework repo:** If `artifact_manifest` exists but is a flat list (not organized into 5 categories), restructure:
     - Entries with `file_path` in `.prawduct/artifacts/` → `artifacts` category
     - Entries with `file_path` in `skills/` → `source_components` category
     - Entries with `file_path` in `templates/` or `tools/` → `tooling` category
     - Entries with `file_path` in `tests/` → `test_specs` category
     - Entries with `file_path` in `docs/` → `human_docs` category
   - If entries lack `depends_on`/`depended_on_by` fields, leave them empty (don't guess)
   - If no `artifact_manifest` exists at all, create one with entries for each discovered artifact file in `.prawduct/artifacts/`

4. **Write updated file** to `.prawduct/project-state.yaml`.

---

### Phase D: Path Reference Updates

**When:** Phase A relocated files (layout migration occurred).

**Steps:**

1. **Scan `artifact_manifest` entries** and update `file_path` values:
   - `artifacts/foo.md` → `.prawduct/artifacts/foo.md`
   - `framework-observations/foo.yaml` → `.prawduct/framework-observations/foo.yaml`
   - `working-notes/foo.md` → `.prawduct/working-notes/foo.md`

2. **Check build plan chunk references.** Build plan chunks typically reference artifact NAMES (not paths), so they should be unaffected. Verify and flag to the user if any use full paths that need updating.

3. **Write updated file** if any paths changed.

---

### Phase E: Build Stage Determination

**When:** Always runs. Sets `current_stage` appropriately for the migrated project.

**Logic:**

```
if build_plan.chunks exists AND any chunk has status "in-progress" or "pending":
    keep current_stage as-is (preserve "building")
elif build_plan.chunks exists AND all chunks have status "complete":
    set current_stage to "iteration"
elif current_stage is "building" but no chunks exist:
    set current_stage to "iteration"
elif current_stage is null or missing:
    set current_stage to "definition"
else:
    keep current_stage as-is
```

---

### Phase F: Artifact Coverage Advisory

**When:** Always runs after migration. Advisory only — presents information, does not auto-generate.

**Steps:**

1. **Read the structural characteristics** from the migrated `classification.structural` section.

2. **List expected artifacts:** 7 universal artifacts + characteristic-specific artifacts (from Artifact Generator amplification rules in `agents/artifact-generator/SKILL.md`).

3. **List discovered artifacts** in `.prawduct/artifacts/`.

4. **Report gaps:**
   > "Your project has [N] artifacts. Based on your structural characteristics ([list]), the current framework would also generate: [list of missing artifacts]. These are optional — you can generate them later with the Artifact Generator."

**This is advisory only** — present to user, don't auto-generate. The user may choose to generate them in a future session.

---

### Phase G: Reflection and Return

**Always runs as the final phase.**

1. **Add `change_log` entry** documenting the migration:
   ```yaml
   - what: "Migrated project from [source description] to v2 format"
     why: "Old schema/layout detected; migrated to current format for full framework governance"
     blast_radius: ".prawduct/project-state.yaml"
     classification: process
     date: <today>
   ```
   Include specifics: what phases ran (layout relocation, schema migration tier, scaffolding), what was moved/mapped/added.

2. **Reflection.** Assess these dimensions:

   | Dimension | Question |
   |-----------|----------|
   | **Coverage** | Did migration handle all aspects of the old format? Were any edge cases discovered? |
   | **Clarity** | Was the migration process clear and predictable, or did it require improvisation? |
   | **Preservation** | Was all user content preserved correctly? Any losses or misinterpretations? |
   | **Learning completeness** | Did this migration reveal gaps in the migration skill that should be documented? |

   **Always record reflection in `change_log`:**
   ```yaml
   - what: "Migration reflection"
     why: "[assessment summary or 'no concerns']"
     blast_radius: meta
     classification: process
     date: <today>
   ```

3. **If substantive findings exist**, run `tools/capture-observation.sh` with `--session-type product_use --stage meta`. Substantive findings include: edge cases not documented, user content lost or misinterpreted, significant improvisation beyond documented steps, or schema mapping ambiguities. "Migration completed successfully" is not substantive.

4. **Present summary to user:** What was moved (Phase A), what was migrated (Phase B), what was scaffolded (Phase C), what paths were updated (Phase D), what stage was set (Phase E), and what artifacts are advisory (Phase F).

5. **Return control to the Orchestrator** for Session Resumption. The project now has a v2 project-state.yaml in `.prawduct/` and can use full framework governance.

---

## Edge Cases

**Mixed content:** If the old file has some v2-compatible sections alongside old-format sections, preserve the v2 sections and only migrate the old ones.

**Corrupt files:** If the file can't be parsed at all, treat as v0 (extract what's readable, re-derive the rest).

**Framework repo:** Migration is never triggered for the framework repo (`self_hosted` scenario). The framework's own project-state.yaml is always maintained at the current schema.

**Layout-only migration:** When `scenario: "migration_layout"` and `schema_version_raw: "current"`, only Phases A, C, D, E, F, G run. Phase B (schema migration) is skipped since the schema is already current.

**Files at both locations:** When project-state.yaml exists at both root and `.prawduct/`, the `.prawduct/` version takes precedence (it's newer). The root version is preserved as a working note for reference.

**Active builds:** Phase E preserves "building" stage when in-progress chunks exist. The build can continue after migration with full v2 governance.
