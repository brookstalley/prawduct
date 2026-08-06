# Upstream Dependency Intake Policy

> **This policy is about dependencies, not package managers.** It governs any upstream
> artifact whose release someone else controls, independent of delivery mechanism.

That sentence is the whole design, and every rule below answers to it. Registry packages are
the obvious case and the least complete one: container base images, CI actions pinned to a
mutable tag, git submodules, vendored directories, install scripts, infrastructure modules,
chart repositories, editor and agent extensions, and downloaded model weights all carry the
same exposure through routes no manifest lists. CI actions are the sharpest case — upstream
code executing with the repository's credentials, referenced by a mutable tag, present in no
manifest at all.

This is the canonical statement of the policy. Every other surface — the discovery section,
the planning and building guidance, the Critic bullet, the doctor check, the janitor theme,
the advisory probe — **cites this file rather than restating it.**

## The six clauses

Each clause is stated in terms of *dependencies*. How each is enforced is the tier model
below; how each is spelled in a given toolchain is the non-normative appendix.

**Clause 1 — Minimum release age.** An upstream release is not adopted until it has been
publicly available for the policy's minimum age. **Framework default: 7 days** for untrusted
upstream. Seven rather than the community-converged ~3 because it is more than double the
observed dwell time of every measured 2026 incident, and because it additionally covers the
*stability* failure mode — a release ships broken and is superseded within days — that no
security-motivated default targets. A product may raise or lower it as a recorded decision
with a why.

**Clause 2 — Trust tiers.** Two, and only two.

- **Trusted** — same repository, same owner, or an explicitly declared party. Taken at
  latest, no minimum age. Each declared party is recorded **with its why**, so the register
  is auditable and revisitable rather than invisible.
- **Untrusted** — everything else. Clause 1 applies.

*Accepted risk, recorded once:* the 2026 campaigns compromised reputable, widely-used
upstreams through maintainer-account compromise, so a declared-trusted third party whose
publishing account is compromised has an unmediated path in. Same-repo and same-owner do not
carry this risk — the product controls the publish and would know. The per-party *why* is the
mitigation that keeps the exposure visible.

**Clause 3 — Security fast path.** A release that fixes a known vulnerability the product is
exposed to is **exempt from the minimum age** and adopted on its merits, immediately. Without
this clause the policy converts a security control into a security regression: a blanket
cooldown delays patching known vulnerabilities. Exercising the exemption is a recorded act,
never a silent one.

**Clause 4 — Install-time execution.** Upstream code is not granted arbitrary execution at
install time by default. Where the toolchain can deny lifecycle or build scripts, it denies
them, and the dependencies that genuinely need them are an allowlist with reasons. This is the
clause that addresses the *observed* payload vector — the 2026 worms executed obfuscated
payloads at install time and self-propagated. Waiting out clause 1 does not stop an install
from running arbitrary scripts once the wait ends.

**Clause 5 — Resolution is pinned and frozen.** The resolved dependency set is committed and
authoritative. Installs in CI, and installs performed by an agent, do not re-resolve — they
install exactly what is pinned. Without this, clauses 1–4 govern the manifest while something
else silently decides what actually lands.

**Clause 6 — New-dependency intake.** Adding a dependency that is new to the product is
governed twice: the **version adopted** must satisfy clause 1 like any other release, and the
**package identity** must be verified to be the one intended. The second half is the
AI-specific vector and the reason this is not folded into clause 1 — an agent can hallucinate
a plausible package name, and attackers pre-register hallucinated names. Verification means
confirming the source repository, publication history, and maintainer are the ones the
decision was made about. **A name that resolves is not a name that was verified.**

## Enforcement tiers

The policy is one statement. What varies is **the strongest mechanism available to enforce
it** — the same shape `project-preferences.md` already uses for norms, where a mechanism is
assigned when the preference is added so it does not quietly become aspirational.

| Tier | Mechanism | Binds | Can express |
|---|---|---|---|
| **1 — Declarative** | The toolchain's own config | **Every actor**: owner, agent, CI, contractor, a script none of them wrote | Clauses 1, 2, 4, 5 |
| **2 — Bot** | The update bot's config | Proposed updates | Clauses 1, 2, **3** — the only tier that can express the fast path |
| **3 — Agent-mediated** | A documented procedure: enumerate available updates, obtain publication times, classify by tier and clause, act | The agent, per invocation | **All six**, including the judgment clauses 3 and 6 |

Three rules govern the tiers.

1. **Prefer the strongest tier the ecosystem allows.** A tier-1 expression binds actors who
   have never read the policy; a tier-3 expression binds one actor on a good day.
2. **Record the tier actually reached, per intake surface.** A policy that claims coverage it
   does not have is worse than an absent one. *"Enforced at tier 3"* is a valid and honest
   recorded state — *"unenforceable"* is not a state this design produces.
3. **Tier 3 is not a consolation prize for ecosystems without declarative support.** It is
   where judgment lives *everywhere*. *"This release is five days old, under our seven, but it
   is the fix for a vulnerability we are exposed to"* is clause 3, and no config key can make
   that call. Tier 1 sets a floor that cannot be forgotten; tier 3 handles the exceptions and
   everything the floor cannot see.

**Tier 3 must be a procedure, not a prompt.** Guidance that lives only in an agent's
instructions is the weakest form of the weakest tier. The deliverable is a policy-derived
update procedure written into the product and built on its runbook machinery: enumerate the
available updates, obtain each candidate's publication time, classify by trust tier and
clause, act. A procedure is auditable and re-runnable by someone who was not there; an
instruction to "check the age first" is neither.

## Recording the policy

The decision lives in `project-state.yaml` under `design_decisions.upstream_dependency_policy`
(sub-keys `minimum_release_age`, `trusted`, `security_fast_path`, `install_time_execution`,
`resolution_pinning`, `new_dependency_intake`, and `surfaces` — per intake surface, the
enforcement tier actually reached). Its rationale, the declared-trusted register with each
party's why, and the per-surface tier record belong in the product's `security-model.md` as a
`## Direction` entry: the policy **binds future work**, which makes it norm-shaped rather than
loose prose.

Setting the top-level `upstream_dependency_policy_decided` fact is what resolves the ambient
nudge for everyone on the next sync.

**The stance is force the decision, don't mandate the answer.** A product that consumes no
upstream code records that in one line and is done; every check in this feature is advisory or
WARNING, and none blocks.

## Appendix (NON-NORMATIVE) — how the clauses are spelled per ecosystem

**This appendix is non-normative.** It accelerates common cases and constrains nothing. Three
consequences follow, and all three are requirements of this policy:

1. **No policy statement, gate, or check may be phrased in terms of a named ecosystem.**
2. **An ecosystem absent from this table is fully covered by the policy** and is enforced at
   the best tier it can reach — in the worst case tier 3, which is always available.
3. **A stale table is a documentation defect, never a coverage gap.** The conformance scan's
   *unclassified* verdict is what keeps an out-of-date table from reading as clean.

The concept below has at least eleven different names across fifteen-plus tools — `cooldown`,
`minimumReleaseAge`, `min-release-age`, `exclude-newer`, `stabilityDays`, `uploaded-prior-to`,
`min-age`, `cooldown-days`, `minimumDependencyAge`, `autoUpdateDelay`, and more. That spread is
the strongest available evidence that the useful artifact is an abstraction with a mapping, not
a config recipe — and it is why this table is an appendix rather than the policy.

**Checked 2026-08-05.** For a maintained cross-tool reference — per-tool key, syntax, default,
and security-exemption status — see [cooldowns.dev](https://cooldowns.dev/). Prefer it over
this table when the two disagree; this one records only what was verified on that date.

| Surface | Clause 1 expression | Tier | Notes |
|---|---|---|---|
| Renovate | `minimumReleaseAge` | 2 | Bypasses cooldown for vulnerability-driven updates — clause 3 expressible. |
| Dependabot | `cooldown` | 2 | Defaults to 3 days from July 2026; bypasses for security updates. |
| pnpm | `minimumReleaseAge` | 1 | On by default from v11. |
| Yarn | *key per the reference* | 1 | Defaults to 1 day from 4.15; only the default was verified. |
| Deno | *key per the reference* | 1 | Defaults to 24 hours from 2.9; only the default was verified. |
| uv | `exclude-newer` | 1 | Accepts relative durations. |
| pip | `--uploaded-prior-to` | 1 | Install-time flag. |
| Go · Maven · Gradle · NuGet · Composer · SwiftPM · pub | *no native support* | 3 | Fully covered by the policy; enforced by the tier-3 procedure. |

**The critical asymmetry:** only update *bots* exempt security fixes from a cooldown. No
package manager surveyed has a native security exemption. A naive blanket cooldown at the
package-manager layer therefore delays patching known vulnerabilities — which is why clause 3
is a first-class clause and why a tier-1-only expression is incomplete rather than ideal.
