# Backlog Service — Security Model

`status: draft v1 — drilled down from backlog-service-prd.md §16.3 (2026-07-16) · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4, esp. O5/D8, PV1–4, CC4, XP2, G1–G5) and
`documentation/backlog-service-data-model.md`. Auth is largely **resolved by O5** — this doc records
those decisions and adds the credential-handling, provenance-trust, and abuse rules the design implies.

**Risk profile (proportional — Principle 11).** A personal/small-portfolio backlog whose backend is
**GitHub itself**. The system *inherits GitHub's authentication and access model wholesale* and its
job is to **not weaken it**. So most of "security" here is one sentence — *delegate to GitHub* — and
the real surface is three things the adapter genuinely owns: **(1) credential handling** (it holds a
token in-process), **(2) provenance trust** (cross-project / anonymous filing lets a stranger write),
**(3) public-submission abuse** (PV3). Everything else is GitHub's problem, deliberately.

**Threat model — what we defend vs. explicitly don't.**
| Defend against | How |
|---|---|
| Leaking a token (logs, cache, export) | §4 — never persist/log tokens; scrub before write |
| A hostile *upstream* / *anonymous* submission (spam, poisoned item, impersonated `source`) | §5 untrusted-until-triaged + §6 abuse controls + retro-governance |
| A human UI edit corrupting encoded state | CC5 reconciliation (Data Model §4) — integrity, not adversary |
| Acting as the wrong identity (git≠gh, cloud proxy, Actions bot) | §1 validate-identity-early + attribute off the API identity |
| **Not defended (out of scope):** GitHub itself compromised; a trusted collaborator with repo write acting maliciously; nation-state; the owner's own laptop compromise | GitHub's model + repo-access trust is the boundary (PV1) |

---

## 1. Authentication (resolved — O5/D8)

**The adapter never manages its own credential — it inherits the session's GitHub auth.** `gh` is the
**required, portable transport** (the one thing that works local + cloud-proxy + Actions); raw HTTP is
an optional fast-path only where a *real* token is in hand.

**Credential resolution, keyed by target owner:**
- **Owned orgs/repos** — the session identity (local `gh`/token; optional GitHub **App** installation
  as a per-owner rate/attribution upgrade — never required to adopt).
- **Public / foreign repos** (upstream/anonymous filing on repos the fleet isn't a member of) —
  **user token** (you can't install an App you don't own). A GitHub account is the only barrier (PV3).

**Identity is context-dependent — "authed as the user" is strictly true only locally:**
| Context | Acts as | Note |
|---|---|---|
| Local interactive | the user's `gh`/token identity | same as their terminal; probe-confirmed |
| Cloud (claude.ai/code) | proxied user via `proxy-injected` | `gh` works; raw-HTTP-from-env does **not** (S1) |
| GitHub Actions | the **Claude App bot** | not the user |

**Token scope (least privilege):** `repo` minimum (local probe confirmed the current token has it);
`read:project`/`project` **only if** Projects-v2 rollup (Q4) is used; **not** `admin:org` unless the
optional App/org-Fields path is adopted. `/prawduct:onboard`/`doctor` (GV5) checks scope and warns on
a gap rather than silently under-functioning.

**Validate identity early.** Because git-push identity can differ from the API identity (probe found a
live `gh`-ssh vs HTTPS-remote split), the adapter resolves and records the **API identity**
(`gh api user`) as the actor for every mutation — never the git-push identity — and surfaces a mismatch
(`gh api user` login vs `git config user.email`) as an advisory rather than acting on a wrong identity.

---

## 2. Authorization & access (PV1 — structural, delegated)

**Per-project visibility inherits repo access, for free.** A private project's backlog is
readable/writable exactly by its GitHub contributors; a public project's is world-readable and
world-filable (PV3). There is **no bespoke access-control layer** — building one would only be a way to
get GitHub's right.

The adapter *exposes a programmatic surface* (CLI/MCP, AG1/AG6), so the OWASP API design failures apply
— but each is **structurally handled by delegating to GitHub**, which must be stated, not assumed:
- **BOLA (object-level authz):** the adapter never fetches an item with elevated credentials on a
  caller's behalf — it acts with the *caller's own* inherited token, so GitHub enforces per-object
  access. The adapter must **not** introduce a shared/service token that could read across a boundary
  the caller can't (this is the D8 "no shared secret" invariant, PV2).
- **Mass assignment:** create/update bind only the documented item fields (§ Data Model 1.1); a request
  can never set `history`, `node_id`, or another actor's attribution.
- **Excessive data exposure:** JSON output returns item fields only; **tokens, auth state, and the
  local cache path are never in adapter output** (§4).

---

## 3. Data privacy (delegated + one local artifact)

- **Backlog content** lives in GitHub and inherits the repo's privacy classification — the adapter
  adds no new data store of record.
- **The only local artifact is the optional cache** (Data Model §6): SQLite, per-clone, **gitignored**,
  `git-common-dir`-keyed. It is *derived* data (a projection of issues the caller can already read), so
  it carries no privacy beyond the repo's — but it **must not** be committed (gitignore-enforced) and
  **must not** contain tokens.
- **Export** (MG2) is plain files of issues the exporter can already read; same classification as the
  source repo. Retention: nothing hard-deleted (DM7); export doubles as backup (G5).

---

## 4. Credential handling (the real adapter-owned surface)

- **Never persist a token.** The token lives only in-process for the life of a call; it is **never**
  written to the cache, export, logs, error messages, or the `prawduct:` block.
- **Handle the cloud placeholder.** In a cloud session the env token is the literal `proxy-injected`
  placeholder — the adapter must **route through `gh`** (which the proxy honors) and must **never** put
  that placeholder (or any token value) into an error it prints.
- **Scrub on the way out.** Any subprocess/`gh`/HTTP error surfaced to the user is filtered for token
  patterns (`gh[opsu]_…`, `Bearer …`) before display — a token in a stack trace is the classic leak.
- **No token in telemetry.** Governance telemetry and the briefing record *counts and identities*
  (login), never credentials.

---

## 5. Attribution & provenance (CC4, XP2)

- **Every mutation records the actor** = the resolved **API identity** (§1) + a per-**agent** marker in
  the payload (assignee/marker), since neither `gh` nor a user token carries agent-level actor identity.
  This replaces git's free audit log (CC4) via the issue timeline + the block.
- **Upstream/cross-project provenance is UNTRUSTED until triaged.** A submitter sets its own claimed
  `source_product`/`version`/`session` (Data Model §1.5) — the adapter records these as *claims*, lands
  the item in `status: submitted` (XP2), and never elevates a submitted item's claimed provenance to
  fact. Triage (a human or a governed worker) promotes it. A `source:` label is a filter, not a
  trust assertion.
- **Anonymous filers** (PV3) are attributed to their real GitHub account — "anonymous" means *no prior
  relationship with the owner*, not unattributed.

---

## 6. Abuse prevention — public submission (PV3/PV4)

Public filing is the one place a party with **no relationship** can write, so it is the abuse surface:
- **Per-project opt-in (PV3).** A repo exposes anonymous filing only if its owner enables it; it is
  **off by default**.
- **Rate-limit + moderate (PV4).** The submission path is rate-limitable and moderatable (spam/abuse
  triage); submitted items are quarantined in `status: submitted`, never straight into working state.
- **Composes with retro-governance (`MET-6T4K`).** Every out-of-band contribution — an anonymous
  filing, a foreign PR, an agent-autopilot branch — is governed on the way in before it can affect the
  backlog or merge. PV4 enablement is **gated on that path existing**; don't flip PV3 on before it does.
- Native GitHub abuse controls (report/block, issue interaction limits, `[bot]` filtering) are the
  first line — the adapter adds triage quarantine, not a parallel moderation system.

---

## 7. The optional GitHub App (only if adopted)

The App is an **optional per-owner rate/attribution upgrade**, not part of the P0 slice — so its
security cost is opt-in. When adopted: the App's **private key is a real secret** (per-owner install),
held by the owner, never shipped in the plugin and never committed; installation tokens are short-lived
(JWT→installation-token), scoped to the install, and revocable. The reproducible floor (`gh`/user
token) requires none of this — which is why the App is optional (GV4/GV5).

## 8. Non-goals
- No bespoke authentication, authorization, RBAC, or session system — GitHub is the identity provider.
- No defense against a trusted repo collaborator acting maliciously, or against GitHub itself.
- No encryption-at-rest beyond what GitHub / the OS provide (the cache is derived, non-secret, local).

## 9. Traceability
PV1→§2; PV2→§1 (no shared secret) / §2 (BOLA); PV3→§6; PV4→§6; O5/D8→§1; CC4→§5; XP2→§5; G1 (no model
in data plane)→ implicit (deterministic adapter); G2 (never-block) → §1 degradation; G4/G5→§3/§7.
OWASP API design failures (BOLA / mass-assignment / excessive-exposure)→§2.
