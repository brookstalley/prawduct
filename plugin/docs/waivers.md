# Intentional Waivers — `prawduct:allow`

A **waiver** is a source-comment pragma that declares a line **intentionally violates a
named principle or check**, with a **mandatory reason**. It marks the violation as
*reviewed and deliberate* — not invisible. The Critic still validates that the waiver is
legitimate; a waiver is "I looked at this and it's intentional, here's why," never a
rubber stamp.

Waivers are the general mechanism that the original `prawduct:ok-broad-except` marker was a
special case of. Instead of inventing a new magic literal for every kind of intentional
violation, there is **one keyword** and an **open, documented vocabulary** of rule ids.

## Grammar

```
<comment-leader> prawduct:allow <scope>/<rule-id> -- <reason>
```

| Part | Meaning | Rules |
|------|---------|-------|
| `<comment-leader>` | The host language's comment syntax: `#`, `//`, `--`, `;`, `%`, `<!--`, `/* */`, … | **Not parsed.** The recognizer scans for the keyword token; it does not care which comment syntax wraps it. Every language has *some* comment, so the scheme is automatically language-agnostic (Python, shell, C#, Java, SQL, HTML, …). |
| `prawduct:allow` | The stable, namespaced waiver keyword | One keyword for *all* waivers, across all scopes and rules. It never changes between prawduct versions. |
| `<scope>` | `prawduct` or `project` | **Whose** principle is being waived — the framework's (`prawduct`) or the consuming repo's own convention (`project`). Required. |
| `<rule-id>` | kebab-case id from that scope's documented vocabulary | e.g. `broad-except`, `legacy-ref`, `duplication`. A *reference* into a registry, not a literal the tooling hard-codes. Required. |
| `-- <reason>` | **Mandatory** human justification | Canonical separator is ` -- ` (two hyphens, ESLint-style). An em dash ` — ` is also accepted (continuity with the legacy `ok-broad-except` spelling). The reason must be non-empty. |

A waiver may list **multiple refs** comma-separated for a line that intentionally trips more
than one rule: `prawduct:allow prawduct/broad-except,project/no-log -- reason`.

## Why one keyword instead of per-rule literals

The point of this design is to be **semantic, not literal**. Compare:

- **Per-rule literals (what we're replacing):** every new waivable thing needs the canary to
  hard-code a fresh magic token (`ok-broad-except`, then `ok-legacy-ref`, then …) *and* a
  detection rule. Adding a waivable rule means editing the recognizer.
- **One keyword + referenced vocabulary (this design):** the recognizer matches the single
  `prawduct:allow` keyword generically and reads the rule-id as **data**. Each check declares
  which ref waives it. Adding a waivable rule is a registry entry + a doc line — the pragma
  *syntax* never changes. The syntax is closed; the vocabulary is open.

## Scopes

A waiver's scope says **whose rule** is being set aside.

- **`prawduct/<id>`** — a principle or mechanical check owned by the framework. The framework's
  governance (canary, Critic) recognizes and validates these.
- **`project/<id>`** — a convention owned by the *consuming* repo. The framework treats these
  **opaquely**: it reads a `project/*` waiver as "intentional, project-owned" and screens it out
  of framework checks, but it does **not** need to know the project's rule ids — validating a
  `project/*` waiver is the project's own linter/Critic job.

This opacity is the key durability property: **a prawduct update can never break a consumer's
waivers**, and a consumer never has to register its rules with prawduct. The two scopes evolve
independently.

### Scope-matching prevents cross-waiving

A check is waived **iff** the waiver's `scope/rule-id` equals the check's own. A
`prawduct:allow project/foo` does **not** silence prawduct's `broad-except` check, and a
`prawduct:allow prawduct/broad-except` does **not** silence the project's `foo` check. Each
check honors only its own ref. A waiver with the wrong (or a malformed) ref simply does not
apply, so the underlying finding resurfaces — a safe failure mode.

## Placement

A waiver applies to:

1. the line it is on (trailing — the common case), **or**
2. the line immediately **above** the offending line (leading — for long lines or verbose
   reasons).

A region form (`prawduct:allow-begin` / `prawduct:allow-end`) is a documented future extension;
it is not implemented today.

## Reviewed, not exempt

A waiver means **a human reviewed this and it is intentional** — it does not make the line
invisible to governance:

- The **reason is mandatory.** A `prawduct:allow <ref>` with no reason is a malformed waiver and
  is itself a finding (the canary reports reason-less waivers; the Critic flags them).
- The **Critic still validates legitimacy.** For `prawduct/broad-except`, the catch must log
  with context and sit at a genuine system boundary. A broad catch that swallows errors silently
  (`except Exception: pass`, empty `catch {}`) is **always** a finding — no waiver can justify
  silencing errors.

## The `prawduct/*` vocabulary

| Rule id | Waives | Maps to | Notes |
|---------|--------|---------|-------|
| `broad-except` | A deliberately broad exception catch at a system boundary | P5 Honest Confidence / P16 Root Cause (error handling) | The original `ok-broad-except`. The catch must log + re-raise/handle at a genuine boundary. |
| `legacy-ref` | A reference to retired / pre-2.0 machinery that must remain because it is required for migration | P12 Scope Discipline ("Unnecessary backwards compatibility") | Use on the few file-sync paths the 1.x→2.0 migration must still name (e.g. `tools/product-hook` in the cutover REMOVE set). Lets audits enumerate every intentional legacy reference with one grep. |
| `duplication` | A deliberate, maintained code/constant duplication | P7-area Design Sound | Use on the `bin/`↔`lib/` mirrors that exist so the hook stays import-light on the hot path; the reason should name the parity test that pins them. |
| `back-compat` | An intentional compatibility shim or fallback | P12 Scope Discipline | For deliberate compatibility code where a real deployment requires it. |

This table is the registry. Add a row when a new framework rule becomes waivable — that is the
only change needed; the pragma syntax is untouched.

## `project/*` — for consuming repos

A consuming repo documents its own waivable conventions in its `project-preferences.md` (or a
`.prawduct/waivers.md`) and annotates code with `prawduct:allow project/<id> -- reason`. prawduct
recognizes the form and stays out of the way. Examples:

```sql
-- prawduct:allow project/full-table-scan -- nightly analytics job; table capped < 10k rows
```
```java
@SuppressWarnings("unchecked") // prawduct:allow project/unchecked-cast -- legacy JSON bridge, typed at boundary
```
```html
<!-- prawduct:allow project/inline-style -- email clients require inline CSS -->
```

## Legacy spelling

`prawduct:ok-broad-except -- reason` is still recognized everywhere and is **equivalent to**
`prawduct:allow prawduct/broad-except -- reason`. New code uses the general form; consumer repos
in the wild that still carry the legacy spelling keep working unchanged.

## How tooling consumes waivers

- **Compliance canary** (session end, `bin/prawduct-hook`): when running a check, it skips lines
  bearing a matching waiver, and separately reports any **reason-less** waivers.
- **The Critic** (`skills/critic/review-protocol.md`): validates that each waiver is legitimate
  (reason present; the violation is genuinely justified at a real boundary).
- **Auditors** (a human or an agent reviewing the tree): `grep -rn 'prawduct:allow prawduct/legacy-ref'`
  enumerates every intentional legacy reference; `grep -rn 'prawduct:allow'` enumerates all
  intentional waivers and their reasons.

## Recognizer API

The single source of truth is `lib/waivers.py` (importable by the hook, the Critic backend, and
any future check):

- `parse_waivers(line) -> list[Waiver]` — every waiver declared on a line (general + legacy).
- `line_waives(line, rule_ref) -> bool` — does this line waive `rule_ref` (e.g. `"prawduct/broad-except"`)?
- `waives(lines, index, rule_ref) -> bool` — does the line at `index` *or the line above* waive `rule_ref`?
- `invalid_waivers(lines) -> list[Waiver]` — waivers missing a reason (malformed; a finding).

`Waiver` carries `scope`, `rule_id`, `reason`, `ref` (`"scope/rule-id"`), and the source `line`.
