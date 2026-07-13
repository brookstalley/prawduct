---
artifact: design
# scope intentionally empty: design note for the kernel-v3 program; plan scope
# is owned by build-plan-kernel-evidence-store.md.
scope:
status: draft 2026-07-12 — owner review pending on D1/D3 (vetoable assumptions)
created: 2026-07-12
depends_on: [kernel-redesign-discovery.md, kernel-inventory-2026-07-12.md]
---

# Kernel v3 — Evidence Store & Deterministic Data Plane (C1 + C2 design)

Design note for the first constituent plan of GOV-4C7X
(`kernel-redesign-discovery.md`). Scope: the **review-evidence family only**
(Critic facts, their gates, their data plane). Test evidence, PR-reviewer
facts, and the C8 promotion gate adopt this store in later plans.

## 1. Consumers' future queries (the schema's requirements)

Per the persisted-format rule (planning.md; learnings), fields are derived
from the questions consumers will ask — enumerated first, elicited from the
actual gate/tooling call sites in v2.3.3:

| # | Consumer | Question the data must answer |
|---|----------|-------------------------------|
| Q1 | PR gate (`check-cumulative-critic` successor) | Does composed review coverage span `merge-base(develop)..HEAD` *at HEAD*, with zero unresolved blocking findings — regardless of the mode label of any single run? |
| Q2 | Stop-hook Critic gate | Does composed coverage span this session's baseline → the current working tree, ignoring non-judgeable files? |
| Q3 | Builder (post-review) | What findings did review R produce, at what severity, against which files — and which are still unresolved? |
| Q4 | verify-resolutions flow | Which blocking findings from prior facts are resolved by the state now under review? |
| Q5 | Cross-checkout session (C5) | Show me every fact any worktree/session of this clone recorded about tree/commit X. |
| Q6 | `review-stats` telemetry (R5) | Reviews per week, roster size, tier, findings counts, block rate — over time. |
| Q7 | Doctor / human debugging | Why did this gate fail? Which facts exist near HEAD, who wrote them, when, from which session/worktree, under which plugin version? |
| Q8 | Version interlock (C7/C9) | Was this record written by a schema this reader understands? If not, what exactly should the operator/agent run? |
| Q9 | Later plans (test evidence, PR facts, C8 policy) | Can new fact kinds live in the same store without rekeying it? |
| Q10 | Consolidation idempotency (CRT-4B7X) | Has the fact for review-id R already been appended? |

Non-requirements (deliberate): "is this record fresher than the session
start?" (mtime freshness dies — coverage at HEAD replaces it); "does the run's
label match the gate's expected mode?" (label matching dies); portability to
other clones (Q2-owner: local-only).

## 2. Decisions

### D1. Store location: inside the clone's git common dir

`<git-common-dir>/prawduct/evidence.jsonl` (via `git rev-parse
--git-common-dir`, resolved absolute). Properties that fall out structurally:

- **Shared by all worktrees of a clone** (Q5, C5) — the git common dir is the
  one filesystem location every worktree of a checkout already shares.
- **Never committed, no gitignore contract needed** — it lives inside `.git`.
  (The propagated-gitignore learning's failure class can't occur.)
- **Isolated between unrelated repos by construction** (R9) — each clone's
  `.git` is its own.
- **Lazily initialized** — an absent file is an empty store (C9 tier 1: no
  migration for any consumer).
- Host/container split: fixed when host and container share the mounted repo
  (same `.git`); separate clones stay separate — accepted under Q2 (local
  per-repo store, no pushable channel).

Alternative rejected: `.prawduct/.evidence.jsonl` per worktree — keeps the
exact worktree-split defect the program exists to fix; a shared path *outside*
the repo (e.g. `~/.prawduct/<repo-id>/`) breaks R9's simplicity and repo
relocation. [ASSUMPTION: writing under `.git/` is acceptable to the owner —
some tooling treats `.git` as opaque | MED impact | owner can override → the
fallback is `.prawduct/../.git/prawduct/` equivalent via a config knob, same
semantics]

### D2. Record envelope: append-only JSONL, schema-versioned per record

```json
{"schema": 1, "kind": "review", "id": "<review-id>", "ts": "<iso8601>",
 "actor": {"session": "...", "worktree": "...", "plugin": "2.4.0"},
 "body": {...}}
```

- **Append-only** (R5 posture): nothing edits or deletes a line; corrections
  are new facts. Single-slot files become derived caches only (D7).
- **`schema` on every record** (Q8, C7): readers accept known versions,
  skip-with-loud-stderr unknown *older* kinds they don't need, and **block
  with the exact remedy** when a gate-relevant record requires a newer reader
  (in-session auto-update skew detection, C9 tier 3).
- **`kind` namespaces the store** (Q9): `review`, `resolution` now;
  `test-run`, `pr-review`, `promotion` reserved for later plans.
- **`id` is fixed at dispatch time** (Q10): consolidate is idempotent —
  a fact with an existing id is never appended twice; readers dedupe by id.
- Concurrency: one `O_APPEND` write per record (single `os.write` of one
  line). A torn final line (crashed writer) is tolerated with a loud stderr
  note and excluded; a malformed *interior* line is excluded the same way —
  exclusion can only make gates stricter (missing coverage), never looser
  (C3: no error path leaves state a reader mistakes for current).

### D3. Facts are keyed by tree SHA, not session recency

A review fact records the **tree it actually saw**. Reviews usually run on a
dirty working tree (acceptance → Critic → commit), so the reviewed state is
captured as a tree object: temp index (`GIT_INDEX_FILE=<tmp> git add -A` +
`git write-tree`) — writes objects only, **never mutates the session's real
index or working tree** (R1). When the subsequent commit is made verbatim,
`HEAD^{tree}` equals the reviewed tree — so a fact recorded pre-commit vouches
for the commit, from any worktree, in any later session. This is what
dissolves mtime freshness, `_record_covers_head`, and the label/chain
machinery at once.

- `base_commit` + `base_tree`: where the reviewed diff started (resolved by
  `resolve-base`, as today).
- `head_tree` (+ `head_commit` when the reviewed state was a commit).
- Rebase/amend changes the tree → coverage gap → re-review. Correct by
  design (post-sync fresh review is already the learned rule); squash-merge
  preserves the tree, so squashed PRs stay covered.

[ASSUMPTION: tree-SHA keying via temp-index write-tree is viable in every
supported topology (worktrees, containers, headless) — chunk 1 spikes it
before anything builds on it | HIGH impact | validated by spike, owner can
veto the whole keying approach]

### D4. Review fact body

Derived field-by-field from §1:

```json
{"base_commit": "…", "base_tree": "…", "head_tree": "…", "head_commit": null,
 "mode": "final", "tier": "standard", "roster": [{"role": "correctness", "model": "…"}],
 "files_reviewed": ["lib/gates.py", "…"], "files_changed": ["…"],
 "findings": [{"fid": "R-1", "severity": "BLOCKING", "title": "…", "files": ["…"]}],
 "counts": {"blocking": 1, "warning": 2, "note": 3}}
```

- `mode`/`tier`/`roster` serve Q6/Q7 (telemetry, debugging) — the gate never
  branches on `mode` (Q1's whole point).
- `files_reviewed` vs `files_changed`: composition checks that every judgeable
  changed file in the edge was reviewed (Q1/Q2); a scoped review that saw less
  than the diff yields a *partial* edge, not a silent pass.
- Findings ride inside the fact (they are the review's atomic judgment
  output, produced by one consolidation); resolutions do not (D5).

### D5. Resolutions are separate facts

`{"kind": "resolution", "body": {"finding": {"review_id": "…", "fid": "R-1"},
"disposition": "fixed|waived", "verified_by": "<review-id or waiver ref>",
"at_tree": "…"}}` — appended by the verify-resolutions consolidation (code),
never by the builder directly. Q3/Q4 become a join: unresolved-blocking =
blocking findings minus resolution facts. Append-only stays intact; a waiver
disposition carries its rationale reference (R7).

### D6. Coverage algebra

Pure functions over the fact set (no I/O):

- A fact contributes an **edge** `base_tree → head_tree`, valid if every
  judgeable file changed in that interval ⊆ `files_reviewed`.
- Code (not storage) contributes **free edges** for intervals whose diff
  touches only non-judgeable files — computed at gate time with **the one
  shared doc-only/non-judgeable predicate** (this plan collapses the three
  divergent implementations flagged in the inventory §3; the CRT-5D8Q
  metadata-boundary disagreement dies here).
- **Coverage(A → B)** = an edge-path from tree(A) to tree(B).
- **Gate verdict** = coverage exists ∧ unresolved-blocking (D5 join, over
  path facts) = 0. PR gate instantiates it as Q1; Stop gate as Q2.
- Composition replaces: `extends_cumulative` chains, mode-label acceptance
  lists, demotion special cases, `_record_covers_head`, doc-only tail rules.

### D7. Single-slot files become derived caches — or die

`.critic-findings.json` survives only as a code-regenerated view of the
latest fact (builders and briefings read it for *content*); **no gate reads
it**. It carries the source fact `id` so staleness is detectable, and it is
written atomically (temp + rename) by consolidate only. `.pr-reviews/`
untouched this plan (adopts the store when PR facts land).

### D8. Deterministic data plane (C2, review path)

Who writes what, at which lifecycle event — models hand judgment to the data
plane as *content*, never as file-format authorship:

| Event | Writer (all code) | Writes |
|---|---|---|
| `critic-begin --mode <m>` | hook CLI | dispatch manifest: roster **derived from mode via protocol config** (not model-authored), review `id`, `base_*`, `head_tree` (D3 capture), `files_changed` snapshot |
| reviewer SubagentStop | `subagent-stop` → consolidate | (unchanged trigger) |
| `critic-consolidate` | hook CLI | merges partials **against the code-written manifest** (missing partial = loud block naming the role), appends the review fact, regenerates the D7 cache |
| verify-resolutions consolidate | hook CLI | resolution facts (D5) |

The v2.3.3 defect site — the coordinator hand-authoring `manifest.json`,
omitting keys, and leaving the previous review's findings looking current
(CRT-W2NV, CRT-J4PM(1)) — is deleted, not patched: the manifest has no model
author anymore. Reviewer *partials* remain freeform-model-written by design
(they are the judgment payload; the partials + deterministic-merge pattern is
reconfirmed — schema-forced output still doesn't exist for plugin subagents).

### D9. Error posture (C3 applied to this plan's surface)

Every error path in the new module set resolves to exactly one of:
**self-heal** (torn tail line), **no-op with stderr attribution** (unknown
older record kind), or **loud block with remedy** (schema-ahead record,
missing manifest role, no coverage path). Enumerated per path in the plan's
chunk tests; the broad-except pragma count in touched modules must not grow.

## 3. What this deletes (no re-implementation elsewhere)

Mode-label matching in the PR gate · `extends_cumulative` chain bookkeeping ·
record-audit protocol prose · `_record_covers_head` · mtime-vs-session
freshness for review evidence · the stale-evidence warning class · two of the
three doc-only predicates · model-authored `manifest.json` and its
hand-patching workaround prose.

## 4. Out of scope (later constituent plans)

Test evidence on the store · PR-reviewer facts + `.pr-reviews/` retirement ·
C8 promotion-policy gate + MIG-6B0R · C6 feedback pull · C9 tiers beyond
what D1/D2 give for free · gate-posture recalibration (C4) beyond the gates
this plan already touches · tripwire deletion (§4.3 — own cleanup plan).

## 5. Do-not-reintroduce check (R10)

Tree-SHA keying here is **not** the retired `git_sha` evidence pinning
(TST-4K2P): that field was dead-read decoration on a timestamp-keyed record —
eyeballed, misleading, judging nothing. Here the tree is the *primary key the
gate computes over*, and no timestamp participates in any gate question.
Content-hash *freshness* stays dead: nothing in D6 hashes file contents to
decide staleness; trees compose, they don't expire.
