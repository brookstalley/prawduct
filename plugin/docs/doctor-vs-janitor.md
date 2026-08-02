# `/prawduct:doctor` vs. `/prawduct:janitor` — the boundary

Both skills are framed as "health checks," so it is easy to assume they overlap. They don't.
This is the canonical statement of what each owns and the rule for deciding where a new concern
belongs. Each skill carries a short `## Scope & boundary` summary that points here; this is the
full version.

## The one-line split

- **`/prawduct:doctor`** — is *prawduct itself* correctly set up and governed in this repo?
  Governance/install **conformance**: install reference, distribution, anchor, core state,
  discovery captured, gitignore contract, recorded decisions. It **reports and guides** — it never
  edits the product's code.
- **`/prawduct:janitor`** — is the *product's own* code, docs, tests, and dependencies well-built
  and current? Codebase **craft maintenance**: it **surveys, then fixes** through the standard
  build cycle (build plan → Critic → reflection).

## Three axes that distinguish them

| Axis | doctor | janitor |
|---|---|---|
| **Subject** | prawduct scaffolding & recorded decisions (`.prawduct/`, `.claude/settings.json`, the CLAUDE.md anchor, the gitignore *contract*) | the product's own source, tests, docs, dependencies, git history |
| **Action model** | report & present the exact edit; never auto-fixes (plus the bounded `prawduct-hook` operations it drives, each owner-invoked — the skill's Health Check flow is their one roster, so this row does not keep a second copy) | survey, then fix through a full build plan + Critic |
| **Question type** | "is X present / recorded / correct?" — conformance, roughly binary | "is X well-built / current / proportionate?" — craft, graded |

A softer fourth axis is **cadence**: doctor is point-in-time (after onboarding/migration, or when
you suspect setup is off); janitor is periodic deep maintenance — fresh eyes on the codebase after
time away.

## Placement rule — which skill owns a new concern

1. Does it ask whether prawduct governance is set up, or a required decision/state is
   *recorded · present · correct*? → **doctor** (a conformance check answered by reading
   `.prawduct/` / `.claude/` / the anchor; reported-and-guided, never auto-fixed).
2. Does it ask whether the product's own code/docs/tests/deps are *well-built · current ·
   proportionate*? → **janitor** (a craft survey resolved by fixing through the build cycle).
3. Does it have **both** facets — a governance-conformance facet *and* a craft-quality facet? →
   **both skills**, but each owns only its facet and cross-references the other. This is the
   exception, not the default; most concerns land in exactly one skill.

## "Legitimately both" — the two worked examples

These are the only concerns that genuinely live in both skills today. In each, the two checks ask
different questions at different altitudes — that is why they are not duplication.

- **API versioning.** doctor Health-Check #9 asks *"is a versioning decision recorded?"*
  (conformance — `design_decisions.api_versioning_approach` set, or an explicit dated deferral).
  The janitor "API Design & Versioning Hygiene" theme asks *"is the API designed to evolve well?"*
  (craft — across ~8 dimensions, of which versioning is one). The recorded decision is the only
  gated part (Critic + the `api-versioning` advisory); the janitor theme is a survey.
- **gitignore.** doctor Health-Check #8 checks the prawduct *contract* (session-file entries
  present; the retired `build-plan.md` entry not re-added). The janitor Version Control Hygiene
  theme checks *general* hygiene (build artifacts, editor files, secrets). Different objects, same
  file.

## Adjacencies that are handoffs, not overlaps

- **Template Currency** (janitor) compares the product's artifacts against the plugin's templates.
  Its own pre-check tells the user to confirm the plugin install via `/prawduct:doctor` when the
  plugin root is unreachable — an explicit handoff, not a shared check.
- **Backlog**: doctor Health-Check #7 reports *external* backlog files (`TODO.md`, `BACKLOG.md`)
  not yet recorded in `backlog_external_imports`; the janitor Backlog-Triage step surveys the
  *prawduct* backlog's own health (stale/unstaged/dedup). Different objects.
