# Adversarial Review (Methodology Guide)

**Read this before invoking `/adversarial` — and before deciding whether to invoke it.**

## Why Adversarial Review Exists

Standard review (Critic) and standard tests answer the same epistemic question: *"Does this code do what the spec says?"* They catch happy-path bugs, spec drift, missing coverage, weak tests, principle violations.

What they don't systematically catch: **what would break this code that the spec didn't anticipate.** Edge cases. Unusual inputs. Adversarial conditions. Corner-of-the-corner-cases.

The builder, the Critic, and the test author all share a goal: make the code work. The Adversarial agent has the opposite goal: make the code break. That goal alignment difference is what produces a different finding profile.

This is additive to existing review, not replacement. Critic still checks spec coverage; Adversarial checks attack surface.

## When Adversarial Review Runs

Adversarial review is **opt-in**. It is not automatic, not universal, and not appropriate for every chunk.

### The opt-in prompt at chunk completion

When a chunk completes its standard cycle (build → tests pass → Critic passes → ready to wrap), the builder asks the user:

> "Chunk complete. This chunk touched [surface taxonomy match: e.g., 'an HTTP endpoint with user input']. Want me to run adversarial review on it before we wrap? (y/n)"

The prompt **only fires when the chunk's diff matches one or more entries in the surface taxonomy** (see below). For chunks that touched only UI tweaks, doc updates, or other non-adversarial-warranted code, the prompt is skipped — no point asking about adversarial review of a CSS change.

The user answers yes or no. No is a perfectly valid answer; not every chunk needs adversarial pass. The user knows their threat model better than the agent does.

### Pre-release sweep (also opt-in)

Before a release tag, the user can invoke `/adversarial --sweep-since-last-release` to run adversarial review across the **union of all surfaces touched in any chunk since the last release**. Catches integration-level edge cases that per-chunk passes miss.

## Defense in Depth — Multiple Surface-Identification Points

A single agent identifying attack surfaces is brittle. Builders forget. Specs underspecify. Surfaces get added accidentally during refactoring. This methodology identifies attack surfaces at **three independent points** in the workflow:

### Point 1: Planning (proactive declaration)
Build-plan chunks declare expected attack surfaces upfront in their structured metadata:

```yaml
- chunk: 12
  title: "Add /api/projects/import endpoint"
  attack_surfaces: [http_endpoint, file_io_user_paths, parser]
- chunk: 13
  title: "Refactor session timer display"
  attack_surfaces: []  # explicit empty list — UI only
```

Empty list is a valid declaration; it documents that the chunk is intentionally not touching attack surfaces. Required field — chunks without an `attack_surfaces` declaration are incomplete plans.

The planning agent (or human) consults the surface taxonomy when writing the build-plan to identify which chunks will touch which surfaces.

### Point 2: Building (verification + prompt)
At chunk-end, the builder:
1. Inspects the actual diff and identifies surfaces touched (from the taxonomy).
2. Compares to the chunk's declared `attack_surfaces`.
3. **If actual ⊆ declared**: normal flow. If any declared surface was touched, prompt for adversarial pass on that surface.
4. **If actual \ declared ≠ ∅** (chunk touched surface it didn't declare): flag as **scope drift** AND prompt for adversarial pass on the union of declared + actual.

The scope-drift case is independently valuable — it tells the user "this chunk grew beyond its plan in a way that has security implications," which is information you want regardless of whether you run adversarial pass.

### Point 3: Critic (independent backstop)
The Critic, when reviewing the chunk, performs an independent attack-surface identification — reading the diff and matching against the taxonomy without seeing what the builder declared or acknowledged. New goal in `agents/critic/SKILL.md`:

> **Goal 8: Attack Surface Identification.** Read the chunk's diff. Identify surfaces from the adversarial taxonomy that the diff touches. Compare to the chunk's declared `attack_surfaces` AND to any record of adversarial pass invocation. **WARNING** if a touched surface was undeclared. **WARNING** if a declared surface had no adversarial pass invoked AND project has `adversarial.enabled: true`. Critic does not run adversarial — only flags. Builder dispositions.

The Critic doesn't make the call about whether adversarial *should* run — that's the user's choice via the wrap-time prompt. But the Critic ensures the user is *informed* about the choice, even if the builder forgot to ask.

### Why three independent points

No single point is sufficient:
- **Planning alone** misses surfaces added during implementation that weren't anticipated.
- **Building alone** misses surfaces the builder didn't notice.
- **Critic alone** misses the proactive-decision benefit of declaring surfaces upfront.

Three points compose: planning declares intent, building verifies + prompts, Critic backstops. The user can rely on the system catching attack surfaces structurally rather than hoping any single agent remembered.

## The Surface Taxonomy

Adversarial review is most valuable when targeted at code that has historically attracted edge-case bugs. The surface taxonomy is a finite list of "adversarial-warranted" code patterns:

| Surface | Examples |
|---|---|
| **HTTP/REST endpoint** | Any function reachable via HTTP from outside the trust boundary |
| **Auth/authz** | Login, token validation, permission checks, session management |
| **Cryptographic operation** | Signing, hashing, encryption, key derivation, random generation |
| **Parser** | JSON, XML, YAML, custom DSLs, regex against user input |
| **File I/O with user-controlled paths** | Upload handlers, path resolution, traversal-prone code |
| **SQL or database query construction** | Any string concatenation or interpolation into a query |
| **External process invocation** | `child_process`, `exec`, shell-out, subprocess |
| **Network I/O to external destinations** | HTTP clients, webhooks, callbacks, third-party APIs |
| **Concurrency primitive** | Locks, queues, semaphores, async coordination, shared state |
| **Resource allocator** | Memory, file handles, sockets, connection pools, threads |
| **User input validator** | Form validation, schema checks, type coercion at trust boundaries |
| **Internationalized text handler** | Encoding, normalization, sorting, RTL, mixed scripts |
| **Time and date arithmetic** | TZ conversion, DST, leap seconds, locale-dependent formatting |
| **Serialization boundary** | Bytes ↔ objects, network protocol parsing, file format encoding |

When the builder is about to ask "should I run adversarial?" — it first checks the chunk's diff against this taxonomy. If any match, ask. If none match, skip the prompt.

The taxonomy is intentionally finite. If a project has unique adversarial surfaces not on this list (e.g., a financial-tech project might add "monetary arithmetic"), it can extend the taxonomy in `.prawduct/adversarial-surfaces.md`.

## Disposition Policy

When adversarial findings come back, **every finding must be dispositioned** — silent ignoring is forbidden.

For each finding, the builder chooses one of:

### 1. Convert to regression test
The finding represents a real edge case the code should handle. Convert the `suggested_test` to an actual test, add it to the suite, ensure the test fails on the current code (proves the finding is real), then fix the code so the test passes. Standard regression-test discipline.

### 2. Dismiss with written rationale
The finding is technically accurate but not in the project's threat model, or the cost of fixing exceeds the benefit. Document the dismissal in `.prawduct/.adversarial-findings.json` with a `disposition: dismissed` and a `rationale` field. Examples of acceptable rationales:
- *"This input is generated by trusted internal code; not reachable from external surface."*
- *"Project explicitly does not support input strings >10MB per docs/limits.md."*
- *"Race condition only manifests under contention >1000 req/sec; project SLA is 100 req/sec."*

Do not dismiss findings with vague rationales like "edge case" or "unlikely." Be specific about WHY this finding is acceptable.

### 3. Escalate to backlog
The finding is real and worth fixing, but is out of scope for the current chunk. Add to `.prawduct/backlog.md` with reference to the finding ID, then disposition as `disposition: escalated_to_backlog`. The next planning cycle picks it up.

After dispositioning, append a learnings entry (`learnings.md`) summarizing what the adversarial pass revealed about this surface. Adversarial passes are a rich source of learnings — what kinds of edge cases keep showing up tells you about your codebase's blind spots.

## Anti-Patterns to Avoid

1. **Adversarial-as-substitute-for-Critic** — they ask different questions; you need both. Critic catches spec drift; Adversarial catches attack surface. Skipping Critic because "we ran Adversarial" is a category error.

2. **Finding fatigue** — too many low-quality findings teach builders to ignore the agent. The "no false positives" discipline in the constitution is the antidote, but the user can also raise the severity threshold in the invocation (e.g., `/adversarial --min-severity=high`) if the agent over-generates.

3. **Adversarial on every chunk** — wastes time on chunks that don't warrant it. The opt-in prompt + surface taxonomy is the gate. If the prompt fires every time, either the project is doing high-risk work consistently (legitimate) or the taxonomy is too permissive (refine).

4. **Adversarial without disposition** — findings that sit unresolved in `.adversarial-findings.json` accumulate as noise. The wrap hook should refuse to wrap a session if any finding is undispositioned (similar to how Critic findings block wrap).

## Integration with Other Review Roles

| Order | Role | Output |
|---|---|---|
| 1 | Builder | Code, standard tests, artifacts |
| 2 | Critic (mandatory) | Findings against spec, principles, coverage |
| 3 | Adversarial (opt-in, prompted) | Adversarial test specifications |
| 4 | Builder | Disposition adversarial findings; convert top picks to tests; fix or escalate |
| 5 | Critic (re-run if material code changed) | Re-validate that adversarial-driven changes don't regress |
| 6 | PR Reviewer (at PR creation) | Release readiness; assesses adversarial coverage as part of overall quality |
| 7 | Janitor (periodic) | Tidy up test suite if adversarial added many new tests |

The Critic and Adversarial agents do not coordinate directly — they're independent. The builder is the integration point that sees both sets of findings and acts on them.

## Configuration

Per-project adversarial settings live in `.prawduct/project-state.yaml`:

```yaml
adversarial:
  enabled: true            # opt-in switch; false disables the prompt entirely
  min_severity: medium     # findings below this threshold are suppressed
  surface_taxonomy: methodology/adversarial-surfaces.md  # path to taxonomy (extensible per project)
  prompt_at_chunk_end: true  # if false, only the explicit /adversarial invocation triggers
  prompt_text: "Want me to attack this chunk? (y/n)"  # customizable wrap-time prompt
```

Defaults to `enabled: false` — the user explicitly opts in per project. New Prawduct projects do not get adversarial review by default.
