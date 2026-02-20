# External Repository Gate — Structural DCP Plan

**Created:** 2026-02-19
**Classification:** Structural
**Motivation:** Cross-repo governance escape — an entire product (worldground) was built without governance because the edit gate treats files outside known repos as "ungoverned" and auto-allows them.

## Root Cause (from PFR)

The gate classifies files into three buckets: framework, product, ungoverned. Ungoverned files auto-allow regardless of governance state. When the Orchestrator wasn't loaded (agent compliance failure), worldground files were classified as ungoverned → all edits passed without activation check, PFR, chunk review, or Critic.

Root cause category: `process_not_enforced` — the gate had an explicit allow-all path for unclassified files in source code repositories.

## Prior Observations

- `2026-02-17-agent-bypassed-orchestrator-activation-by-writing.yaml`: Related — markers can be created via Bash. Same governance perimeter gap family.

## Design

### Key insight

The gate should distinguish between "file not in any source repository" (temp files, downloads — allow) and "file in a git repository that isn't registered" (the worldground case — block). Git repo detection is the discriminator.

### Block message design

When blocking, steer the user toward clear options:
- "This repository isn't onboarded to Prawduct. To continue: (1) onboard it with `prawduct-init`, or (2) restart Claude Code without Prawduct hooks."
- This is user-facing language, not developer-facing. The LLM reading the block message should relay it to the user.

### Changes by file

#### Phase 1: classify.py + gate.py (core fix)

**classify.py:**
- Add `is_external_repo: bool` to `FileClass` dataclass
- Add `_find_git_root(file_path) -> str | None` helper: walks up directories looking for `.git`, returns the root or None
- In `classify()`: after existing classification, set `is_external_repo = True` when:
  - File is in a git repo (git_root is not None)
  - AND that git repo is not `ctx.framework_root`
  - AND file is not `is_product` (not in the active product directory)
- Cache git root lookups by directory prefix to avoid repeated walks

**gate.py:**
- In `_check_edit()`, replace the current ungoverned pass-through (lines 87-90):
  ```python
  # Current:
  if not fc.is_framework and not fc.is_product:
      return Decision(allowed=True)

  # New:
  if not fc.is_framework and not fc.is_product:
      if fc.is_external_repo:
          return _check_external_repo(fc, ctx, state)
      return Decision(allowed=True)
  ```
- Add `_check_external_repo()` function:
  - If governance is active (activation marker exists and valid): BLOCK with actionable message
  - If governance is not active: BLOCK with activation-first message
  - Both cases block — if prawduct hooks are running, you're in a prawduct context

**Block messages:**
- Governance active: "BLOCKED: This file is in a git repository ({repo_name}) that isn't onboarded to Prawduct. Either onboard it: `python3 {framework_root}/tools/prawduct-init.py --json {git_root}`, or restart Claude Code without Prawduct if you don't want governance for this repo."
- Governance not active: "BLOCKED: Prawduct hooks are active but the Orchestrator hasn't been loaded (HR9). Read {framework_root}/skills/orchestrator/SKILL.md first. If you don't want Prawduct governance, restart Claude Code without Prawduct hooks."

#### Phase 2: prompt.py (advisory strengthening)

**prompt.py:**
- After the existing activation check, add product-context validation:
  - If activation IS present, check whether `.active-product` resolves to a directory with `.prawduct/`
  - If it doesn't resolve (file missing, target dir missing, or target .prawduct/ missing): inject advisory about product registration being incomplete

#### Phase 3: Documentation + governance

- Update `.prawduct/artifacts/governance-mechanisms.md` — add external-repo gate to enforcement chain documentation
- Capture observation for the worldground escape via `tools/capture-observation.sh`
- Final Critic review of all changed files
- DCP retrospective

## Blast Radius

- `tools/governance/classify.py` — new flag + git detection
- `tools/governance/gate.py` — new gate path for external repos
- `tools/governance/prompt.py` — product-context advisory
- `.prawduct/artifacts/governance-mechanisms.md` — enforcement chain docs
- `.prawduct/project-state.yaml` — change_log entry

## Risk Assessment

- **False positives:** Minimal — only blocks files in git repos, not temp/download files. The git-repo walk is lightweight (stat calls).
- **Performance:** Git root detection is O(depth) stat calls per unique directory, cached. Negligible overhead.
- **Backwards compatibility:** No breaking changes. Existing governed files (framework + product) follow the same paths. Only new behavior is for files that were previously auto-allowed.
