# Backlog Service — Security Model

`status: draft v2 — independent-review fold (2026-07-16): Actions untrusted-trigger escalation defended + §1↔§2 contradiction resolved (F1); credential scrub upgraded to structured/allowlist-first, denylist extended to fine-grained-PAT/refresh/JWT/URL-embedded (F2); provenance trust stated precisely — every prawduct: block field is self-asserted & forgeable by any write-capable actor, + id: alias collision guard (F3); cache authorizes at fetch not read → scoped to the fetching identity's access boundary (F4); content-borne secrets acknowledged, cache reclassified as sensitive-as-its-bodies, gitignore-is-not-enforcement (F5); PV3 gate made structural (F6); anonymous-quarantine mechanism specified + reconciled with Data Model §3 (F7); never-prompt mechanized, idempotency claim narrowed, identity resolved once/process, "never persist" scoped to adapter, cloud least-privilege clarified (N1–N5). Prior v1: initial drill-down + §1a unattended path. · source: planning session · stage: design`

**Parent:** `documentation/backlog-service-prd.md` (PRD v4, esp. O5/D8, PV1–4, CC4, XP2, G1–G5) and
`documentation/backlog-service-data-model.md`. Auth is largely **resolved by O5** — this doc records
those decisions and adds the credential, provenance-trust, and abuse rules the design implies.

**Risk profile (proportional — Principle 11).** A personal/small-portfolio backlog whose backend is
**GitHub itself**. The system inherits GitHub's authentication and access model wholesale; its job is to
**not weaken it**. So most of "security" is one sentence — *delegate to GitHub* — and the real surface
is what the adapter genuinely owns: **credential handling**, **provenance trust**, **public-submission
abuse**, and the **two runtime contexts where the adapter does NOT act as the caller** (cloud proxy,
Actions bot). Everything else is GitHub's problem, deliberately.

**Threat model — what we defend vs. explicitly don't.**
| Defend against | How |
|---|---|
| Leaking a token (logs, cache, export, error text) | §4 — structured errors + extended scrub |
| **Content-borne secrets** (a pasted `.env`/log in an issue body → cache + export) | §3/§5 — cache reclassified sensitive; **uncommittable by location** (inside `.git`), superseding the doctor gitignore check (W1) |
| A hostile *upstream*/*anonymous* submission (spam, poisoned item, forged `source`) | §5 untrusted-until-triaged (permission-enforced for non-collaborators) + §6 |
| **Actions untrusted-trigger escalation** (a stranger's PR/comment → bot-privileged write) | §1b — no write under untrusted-triggerable events; bot scope is the ceiling |
| **Cross-access-boundary cache read** (broad fetch → narrow reader) | §3/F4 — **vacuous as built** (one repo per store, W1); the fetching-identity scoping + cross-repo revalidate-on-read are what a widening would owe |
| A human UI edit corrupting encoded state | Data Model §4 CC5 reconciliation (integrity, not adversary) |
| Acting as the wrong identity (git≠gh, cloud proxy, Actions bot) | §1 validate-early + attribute off the API identity |
| **Not defended:** GitHub compromised; a trusted repo-write collaborator acting maliciously; nation-state; the owner's laptop compromise | GitHub's model + repo-access trust is the boundary (PV1) |

---

## 1. Authentication (resolved — O5/D8)

**The adapter never manages its own credential — it inherits the session's GitHub auth.** `gh` is the
**required portable transport**; raw HTTP an optional fast-path only where a *real* token is in hand.

**Credential resolution, keyed by target owner:** owned orgs/repos → the session identity (optional
**App** install as a per-owner upgrade); public/foreign repos → **user token** (a GitHub account is the
only barrier, PV3).

**Identity is context-dependent — "authed as the user" is strictly true only locally:**
| Context | Acts as | Note |
|---|---|---|
| Local interactive | the user's `gh`/token identity | same as their terminal (probe-confirmed) |
| Cloud (claude.ai/code) | proxied user via `proxy-injected` | `gh` works; raw-HTTP-from-env does **not**; scope is the **proxy's** to set (N5) |
| GitHub Actions | the **Claude App bot** — **not the caller** (see §1b) | write-scoped; an escalation surface, not just an attribution fact |

**Token scope (least privilege):** `repo` minimum (probe-confirmed locally); `read:project`/`project`
only for Q4; not `admin:org` unless the App/org-Fields path is adopted. **Enforced locally** by the
`/prawduct:onboard`/`doctor` scope check; **in cloud the `proxy-injected` token's scope is the proxy's
responsibility** — the adapter can't guarantee `repo`-minimum there and must not assume it (N5).

**Validate identity early, resolve once.** git-push identity can differ from the API identity (probe
found a live `gh`-ssh vs HTTPS-remote split), so the adapter records the **API identity** (`gh api
user`) as the actor and never the git-push identity, and surfaces a mismatch as an advisory. Resolve
`gh api user` **once per process and reuse it** — per-mutation resolution adds a read per write against
the 5k/hr core budget in a bulk sweep (N3).

### 1a. Unattended operation — no human present

The background-worker persona (PRD §2) and the async briefing refresh (GV2) run with **no human to
re-authenticate or approve**:
- **Identity is whatever the runtime provides; the adapter never prompts.** Mechanized, not asserted
  (N1): the adapter runs `gh`/subprocesses with `GH_PROMPT_DISABLED=1`, `GH_NO_UPDATE_NOTIFIER=1`,
  `GH_PAGER=` (no pager), non-interactive flags, and **no inherited TTY** — so there is nothing to hang
  on. It never triggers an interactive `gh auth login`.
- **Auth failure fails clean, never hangs (G2)** — degrades like the current briefing (broad-caught →
  skipped): fail fast with a retryable logged error; reads fall back to cache-or-"unavailable".
- **Automated actors are marked (CC4):** every unattended mutation carries `automated: true` + a
  worker marker so a bulk sweep isn't misattributed to the human. *(This marker is self-asserted —
  §5/F3 — trustworthy for audit only insofar as the acting identity is; the Actions bot already
  attributes as `[bot]`.)*
- **Idempotency is narrow (N2):** only the migration import is idempotent (keyed on the `id:` alias,
  skip-if-exists). A general unattended *create* is **not** idempotent — a retried/overlapping
  scheduled job would duplicate — so unattended creates that can retry must carry an idempotency key
  (e.g., a dedup marker), or the job must be single-flighted.
- **Self-limiting:** unattended writes self-pace under the ~500/hr content cap and are reversible
  (DM7). **Scope:** acts only where the runtime identity already has access — no unattended
  anonymous/foreign filing (PV3 is attended, human-supplied token).

### 1b. GitHub Actions context — untrusted triggers (F1, load-bearing)

In Actions the actor is the **Claude App bot, not the caller** (§1) — so §2's "acts with the caller's
own token" does **not** hold here, and this is an **escalation surface**, not just attribution. Under an
untrusted-triggerable event (`pull_request_target`, fork-PR, `issue_comment`), the *triggerer* can be an
anonymous external contributor while the *actor* is the write-scoped bot — the classic "pwn request".
**Constraint:** the adapter's **write** paths must not run under untrusted-triggerable workflow events
without an explicit **triggering-actor authorization check** (is the triggerer a repo collaborator?);
the App bot's granted scope is the **privilege ceiling, not the triggerer's**. §1a's unattended-write
capability is **withheld** from untrusted-triggered runs. (Read-only reporting under such triggers is
fine.)

---

## 2. Authorization & access (PV1 — structural, delegated, with two carve-outs)

**Per-project visibility inherits repo access, for free** (PV1) — no bespoke access layer. The adapter
exposes a CLI/MCP surface (AG1/AG6), so the OWASP API design failures apply, handled by delegation —
**except** where the adapter does *not* act as the caller:
- **BOLA (object-level authz):** the adapter acts with the **caller's own** inherited token, so GitHub
  enforces per-object access — **and must introduce no shared/service token** that could read across a
  boundary the caller can't (PV2). **Two carve-outs:** (a) in **Actions** the actor is the bot, not the
  caller — see §1b; (b) the **cache** is a read-store that can serve *across* the fetch-time boundary —
  see §3/F4. Both are stated so the "caller's own token" claim isn't overread.
- **Mass assignment:** create/update bind only documented item fields; a request can never set
  `history`, `node_id`, or another actor's *GitHub-native* attribution. *(But `prawduct:`-block fields
  are body text and therefore self-set by any write-capable actor — §5/F3.)*
- **Excessive data exposure:** JSON output returns item fields only; **tokens, auth state, and the
  cache path are never in output** (§4).

---

## 3. Data privacy (delegated + one local artifact with real sensitivity)

- **Backlog content** lives in GitHub and inherits the repo's privacy — the adapter adds no store of
  record.
- **The cache is NOT "derived, non-secret" (F5).** It stores issue bodies/comments verbatim
  (`item.body`, `item_fts`, `comment.body`) — and a bug tracker routinely holds pasted logs, stack
  traces, and `.env` fragments containing secrets. So the cache is **as sensitive as its most-sensitive
  stored body**, and unlike GitHub it has **no access control at rest**. Therefore: it must never be
  committed, and export (G5/MG2) carries the same sensitivity as its source repo.
  **[W1 DISPOSITION — the gitignore obligation is retired, not merely satisfied.]** This bullet
  previously argued that *gitignore is not enforcement* (an `add -f` or a differing global ignore can
  commit the file) and therefore that `/prawduct:doctor` must verify the cache path is actually
  ignored. W1 removed the premise rather than meeting it: the store lives at
  `<git-common-dir>/prawduct/backlog-cache.sqlite3`, **inside `.git`**, so there is no ignore contract
  to get wrong and `add -f` cannot reach it either. The doctor check has nothing left to catch and is
  not owed — building one would be a control with no yield. The sensitivity classification above is
  unchanged; only its enforcement mechanism moved from a check to the location.
- **Fetch-time vs read-time authorization (F4).** **[W1 DISPOSITION — the exposure is made vacuous,
  and the mitigations below are what a *widening* would owe.]** As built, the store holds items from
  exactly the one repo named in `backlog_service_repo`, so there is no cross-owner content in it to be
  read back by a narrower identity. That is a deliberate narrowing recorded at `cache.py`'s
  "One repo per store" docstring, and widening it is a **design change, never a config flag** —
  whoever widens it inherits every requirement in this bullet, which is why the bullet stays here in
  full rather than being deleted as answered. The analysis, stated for that case: a
  `git-common-dir`-keyed store that can
  hold items from **multiple repos/owners** (`id = owner/repo#number`) has access checked by the
  **fetching** identity at fetch time, not the **reading** identity at read time — so a broad-identity
  fetch (a Q4 fan-out) could later be read by a **narrower** identity in the same clone (a second agent,
  a differently-scoped cloud `proxy-injected` token, or after access to one repo is revoked). Rule:
  **cache entries are scoped to the fetching identity's repo-access set**, cross-owner items fetched
  under a broad identity are **not** reused by a narrower one, and any cross-repo entry **revalidates on
  read** (a re-fetch 404s if access is gone). This keeps the cache from reintroducing the cross-boundary
  read PV2 forbids for tokens.

---

## 4. Credential handling (the real adapter-owned surface)

- **Structured errors are the primary control (F2).** Tokens never reach the error-formatting path:
  the adapter builds errors from known fields, not by echoing raw `gh`/subprocess/HTTP output. A
  denylist scrub is only the **backstop** (the doc's own "classic leak" warning is why it can't be the
  primary defense).
- **Backstop scrub patterns (extended, F2):** `gh[opsu]_…`, **`github_pat_…`** (fine-grained PAT —
  central to D8), **`ghr_…`** (refresh), **bare JWT `eyJ…`** (the App path mints these, §7), and
  **URL-embedded creds** `://[^/@]+:[^/@]+@` (`https://x-access-token:TOKEN@…` — how `gh`/git surface a
  token mid-URL). The App **private key** (§7) gets the same treatment.
- **Cloud placeholder:** in cloud the env token is the literal `proxy-injected` — route through `gh`;
  never emit it (or any token value) in output.
- **"Never persist a token" is *adapter*-scoped (N4).** By *requiring* `gh`, the token is persisted by
  `gh` in `~/.config/gh/hosts.yml` (where the probe read it) — that is `gh`'s store, by design. The
  invariant is: **the *adapter* never writes a token** to the cache, export, logs, telemetry, or the
  `prawduct:` block. Telemetry records identities (login) + counts, never credentials.

---

## 5. Attribution & provenance (CC4, XP2 — trust boundary stated precisely, F3)

**Only the GitHub API identity is trustworthy.** Every `prawduct:`-block field — `source`, the
per-agent/`automated:` marker, provenance, an `id:` alias — is **body text and therefore self-asserted
and forgeable by any actor with write access** to the repo. So:
- **Attribution** = the resolved **API identity** (§1) for the *who*; the payload agent marker is an
  *unauthenticated self-assertion* useful for audit only as far as the acting identity is trusted (CC4).
- **"Untrusted until triaged" (XP2) is GitHub-permission-enforced for the case that matters:** a
  **non-collaborator** (anonymous/foreign filer) can open an issue and comment but **cannot set labels
  or assignees**, so they cannot self-promote out of `submitted` or forge a `source:`/`id:` label. For a
  **write-capable** actor (cross-project filing into an owned repo the fleet is a member of), the
  quarantine is **convention-only** — such an actor *can* set `status:`/`stage:`/`source:`/`id:`
  labels and forge the block. In the all-personal portfolio these actors are the owner's **own agents**
  (moderate stakes), but the boundary is stated, not overclaimed.
- **`id:` alias collision guard (F3 + Data Model §5):** an `id:PFX` must resolve to exactly one live
  item; a *second* item asserting an existing alias is **rejected/flagged**, so ref resolution can't be
  hijacked by a forged `id:` label.
- **Anonymous filers** (PV3) are attributed to their real GitHub account — "anonymous" = *no prior
  relationship*, not unattributed.

---

## 6. Abuse prevention — public submission (PV3/PV4)

- **Per-project opt-in, structurally gated (F6).** PV3 is **off by default**; the enable path (the
  `onboard`/`doctor` toggle) **refuses to turn anonymous filing on unless the governed-intake path
  (`MET-6T4K`) is configured** — a *structural* gate, not a documented "don't." PV4 enablement depends
  on it.
- **Quarantine mechanism, specified (F7).** A non-collaborator cannot apply labels, so an anonymous
  filing arrives **unlabeled** — that **unlabeled state *is* the quarantine**. It is **surfaced to
  triage** (a submitted-intake query lists non-collaborator-authored unlabeled issues — *specified
  here, not yet implemented*: the shipped `list --untriaged` selects on unlabeled alone and so returns
  a superset, over-including the owner's own unlabeled issues rather than missing an anonymous one),
  reconciling with
  Data Model §3 "ignore unlabeled": *ignore* means "not treated as a live backlog item," **not**
  "invisible" — the intake query and the human/governed triage worker see it and stamp `status:
  submitted` (or drop it). No mutation happens under the filer's own identity.
- **Rate-limit + moderate:** GitHub-native abuse controls (report/block, issue interaction limits,
  `[bot]` filtering) are the first line; the adapter adds triage quarantine, not a parallel moderation
  system.

## 7. The optional GitHub App (only if adopted)
Opt-in per-owner upgrade — not in the P0 slice. Its **private key is a real secret** (owner-held, never
shipped/committed; scrubbed like any credential, §4); installation tokens are short-lived
(JWT→installation-token, scoped, revocable). The reproducible floor (`gh`/user token) needs none of this
— which is why the App is optional (GV4/GV5).

## 8. Non-goals
- No bespoke authentication, authorization, RBAC, or session system — GitHub is the identity provider.
- No defense against a trusted repo-write collaborator acting maliciously, or against GitHub itself.
- No encryption-at-rest beyond what GitHub/the OS provide — but the local cache is **content-sensitive**
  (§3/F5), so it is **uncommittable by location** — it lives inside `.git` rather than beside the
  working tree, which is a structural guarantee rather than the gitignore verification an earlier
  draft of §3/F5 called for (W1 disposition, recorded there).

## 9. Traceability
PV1→§2; PV2→§1 (no shared secret) / §2 (BOLA) / §3 (cache boundary, F4); PV3→§6; PV4→§6; O5/D8→§1/§1b;
CC4→§5/§1a; XP2→§5; G1→ implicit (deterministic adapter); G2 (never-block)→§1a + §1 degradation;
G4/G5→§3/§7. OWASP API design failures (BOLA/mass-assignment/excessive-exposure)→§2 (with the Actions
§1b + cache §3 carve-outs). Coherence with Data Model: §5 alias guard↔DM §5; §3 cache sensitivity↔DM §6;
§6 quarantine↔DM §3.
