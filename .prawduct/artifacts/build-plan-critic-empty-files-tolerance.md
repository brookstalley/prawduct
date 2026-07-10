<!-- Build Plan — critic-consolidate tolerates `files: []` on a finding. -->
---
artifact: build-plan
version: 2
scope: critic-empty-files-tolerance
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Root cause is known and verified from a downstream report (discodon). `critic-consolidate` fail-closed on a reviewer partial whose finding carried `"files": []`, because `validate_partial` required a *non-empty* list whenever the `files` key was present. An empty `files` list and an omitted key are semantically identical ("this finding isn't about a specific file"); reviewers are only *told* to omit the key, and a model naturally emits `[]`. Fail-closing the entire consolidation over that distinction is the silently-lost-review failure class the module exists to prevent. Fix: accept an empty `files` list; `[]` is already normalized away downstream by `merge_findings` (only truthy files are kept), so `[]` and omission produce byte-identical canonical records.

**Open assumptions / unknowns:** None consequential. The non-empty requirement is retained where it must hold (`goals`, `roster`, `files_reviewed`).

**What would raise confidence:** N/A (High).

## Status

- [ ] Chunk 01: Accept empty `files` list on a finding without fail-closing consolidation
Context: **Done** (Critic final: 0 blocking, 0 warning, 1 note — change-log entry added). `lib/critic_consolidate.py`: new `_str_list` helper (possibly-empty list of non-empty strings); `validate_partial` uses it for the per-finding `files` field instead of `_nonempty_str_list`. `tests/test_critic_consolidate.py` +3 regression tests (`[]` accepted, list-with-empty-string rejected, `[]` normalized out of the canonical record). 1611 tests pass.

## Build Chunks

### Chunk 01: Accept empty `files` list on a finding without fail-closing consolidation

- **Description:** `validate_partial` treats a finding's optional `files` field as a possibly-empty list of non-empty strings (was: non-empty list when present). An empty list is accepted and normalized away downstream, so a process/evidence finding that carries `"files": []` no longer aborts the whole consolidation. Genuine defects — a non-list, or a list containing an empty string — are still rejected. The non-empty requirement stays on `goals`, `roster`, and `files_reviewed`, which must never be empty.
- **Deliverables:**
  - `lib/critic_consolidate.py`: `_str_list` helper; `validate_partial` per-finding `files` check relaxed to `_str_list`; explanatory comment on why `[]` is tolerated.
  - `tests/test_critic_consolidate.py`: `files: []` accepted; list with an empty string rejected; `[]` normalized out of the canonical record (`merge_findings` produces a record with no `files` key).
- **Tests:** the above; full suite green.
- **Acceptance criteria:** a reviewer partial whose finding has `"files": []` validates and consolidates; the canonical record omits `files` for that finding; a finding whose `files` list contains an empty string still fails validation. Suite green.
- **Critic mode:** final
- **Type:** code
- **Done when:** 1. Acceptance + tests pass · 2. `/prawduct:critic` blocking resolved · 3. committed · 4. `/prawduct:critic cumulative` (the `/prawduct:pr` gate).
