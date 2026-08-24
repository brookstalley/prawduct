---
artifact: build-plan
version: 2
scope: onboard-install-verification
branch: fix/onboard-verify-plugin-install
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "the plugin writes nothing into a governed repo except its own state and the files it reconciles → conforms (this work is read-only against ~/.claude and writes nothing new into the target)"
      - "authority fails closed; advice fails soft → conforms (the install check is advice: it never changes an exit code)"
  - artifact: nonfunctional-requirements
    dispositions:
      - "a new control must name its expected yield and emit it observably → exception, inheriting doctor Health Check #13's shape (clock #563): the new doctor check names its yield in the check itself and cannot emit a fact because doctor has no fact-emitting path at all; building one for a single check is the disproportion the norm exists to prevent"
  - artifact: api-contract
    dispositions:
      - "published surfaces are exactly `version` and `print-install-reference` → conforms (nothing here joins the published tier; `init-product --json` stays internal)"
      - "lifecycle commands default to dry run → conforms (`init-product` keeps `--apply`; the new read mutates nothing in either mode)"
partition: serial — one chunk, one builder; nothing here is independent enough to fan out
last_validated: 2026-08-24
---

## Requirements Confidence

**Level:** High

**Why:** The failure is reproduced and root-caused in `#710` with the mechanism confirmed against
this machine's `installed_plugins.json`; the design obligation already exists in prose
(`lib/install_reference_probes.py` "Known limit" says doctor *can* read the machine-level file and
that the two checks are complementary — doctor just never did it).

**Open assumptions / unknowns:**

- [ASSUMPTION: Claude Code matches a project-scoped plugin install by **exact** `projectPath`, not
  by directory prefix | MED impact | falsifiable]. Not verified: the CLI ships as a packed binary
  with no readable resolution logic, and the machine available for testing carries a `user`-scope
  prawduct entry that would mask any prefix behavior. The design is built to be **safe under either
  answer** — see "Fail toward alarming" below — so resolving it changes a message, not a mechanism.
- [ASSUMPTION: `--dangerously-skip-permissions` is what suppressed the install prompt in the field
  report | LOW impact | unverified and deliberately not relied upon]. The check is **cause-agnostic**
  — it reads the resulting state, never the event that produced it, the same stance
  `install_reference_probes` takes and for the same reason.

**What would raise confidence:** a two-repo experiment on a machine with no `user`-scope prawduct
entry (install project-scope in a parent dir, open a child repo, observe whether the plugin loads).
Worth doing if the exact-match assumption ever produces a false alarm in practice.

## Status

- [ ] Chunk 01: onboard verifies the install, and the surfaces that read it
Context: Plan written 2026-08-24 on `fix/onboard-verify-plugin-install`; baseline suite green
before any edit. Single chunk by design — see "Why one chunk" below. Nothing committed yet.

## Why one chunk

An earlier draft split this into a mechanism chunk and a surfaces chunk. They are a useful split
for a *reader* and a bad one for a *reviewer*: the surfaces exist only to render the mechanism's
answer, so a `chunk` review of the mechanism followed by a `cumulative` over both would read the
same code twice for no new judgement. Review wall clock is the binding cost here (reviewers run on
opus), so the split collapses and the branch gets exactly one `cumulative` review. The two halves
survive as the deliverable list below.

## Design

### The gap

A repo's committed `.claude/settings.json` declares **enablement**; `~/.claude/plugins/installed_plugins.json`
records **installation**, keyed by `(scope, projectPath)`. Onboard writes the former and treats it as
the latter (`lib/init_product.py` `_install_reference_present` checks settings.json only, and doctor
Health Check #1 grades the same file). When installation never happens for the target path, the repo
looks fully onboarded and every governance surface is inert: no banner, no `/prawduct:*` skills, no
Stop-hook gates.

Nothing in prawduct reads `installed_plugins.json`. That is the whole defect.

### Why onboard is the exposed path and migrate is not

`/prawduct:migrate` runs **in** the target repo — invoking it proves the plugin resolved there.
`/prawduct:onboard <target>` runs in a *different* repo's session and scaffolds a target whose own
session has never proved anything. Onboard is the only entry path that can leave a repo scaffolded
and unloaded, which is why the mechanism goes there and not in `migrate`.

### Where the check may live

The hook runtime does not leave `${CLAUDE_PROJECT_DIR}` (`kernel-redesign-discovery.md`), so an
ambient probe cannot see machine-level state — that is exactly the limit
`install_reference_probes.py` documents. `init-product` is not a hook: it is a CLI command the
onboard skill invokes with an explicit target path, and it already writes outside the current
project dir. Reading the operator's own `~/.claude/plugins/` from there is a read, never a write, so
it stays inside the trust decision that running prawduct represents.

### Fail toward alarming

The check reports **installed** only on an exact resolved-path match or a `user`-scope entry. An
ancestor-directory entry is deliberately *not* accepted as covering. The two error directions are not
symmetric: a false alarm costs one idempotent `claude plugin install` command, while a false all-clear
recreates the ungoverned repo this work exists to prevent.

### Not a hard failure

Absence does **not** fail the exit code. The scaffold genuinely succeeded — the repo's state is
correct and portable — and installation for one path on one machine is a separate fact. Conflating
them would make a correct scaffold report broken and would break `--json` consumers. Instead the
status is a first-class field in the result and a loud closing stanza that *replaces* the misleading
"Done. Open the target in a new Claude Code session" line, which today is spoken with full confidence
in precisely the state where it is false.

### Tri-state, not boolean

`installed` / `not installed` / `not checked`. An unreadable or malformed `installed_plugins.json` is
"could not ask", never "fine" — the same rule doctor already applies to its `git check-attr` check,
for the same reason: an empty answer and an absent one are indistinguishable otherwise.

### Rejected: writing `.prawduct/.prawduct-version` at onboard time

`#710`'s third suggestion. The marker is written by the **banner hook** (`hooks/banner.py`
`write_marker`), i.e. only when the plugin actually loads, so its absence is the only on-disk trace
distinguishing "never loaded" from "loaded at least once". Writing it at scaffold time destroys that
signal to gain nothing. Not doing it.

## Build Chunks

### Chunk 01: onboard verifies the install, and the surfaces that read it

- **Description:** Give prawduct a machine-level read of `installed_plugins.json`, wire it into the
  scaffolder so onboard's own output tells the truth, and close the loop for the two readers who
  arrive after the scaffold — the agent opening the repo cold and the operator running doctor.
- **Depends on:** none
- **Artifacts consumed:** `lib/install_reference_probes.py` "Known limit" (the stated design
  obligation this chunk discharges — doctor *can* read the machine-level file and never did)
- **Deliverables:**
  - new `plugin/lib/plugin_install.py` — `config_home`, `installed_plugins_path`, `remedy_for`,
    `install_status`
  - `plugin/lib/init_product.py` — `install_status` in both result dicts (including the
    already-scaffolded no-op path), a human formatter, and a closing line that no longer promises
    governance it cannot deliver
  - `plugin/lib/migrate_plugin.py` — `STATIC_ANCHOR` gains the missing-banner self-check
  - `plugin/skills/doctor/SKILL.md` — Health Check #19, machine-level install (ungraded; it
    cannot see the total failure and `--plugin-dir` self-hosting reads as absent)
  - `plugin/skills/onboard/SKILL.md` — the verification step and its remedy
  - `plugin/lib/install_reference_probes.py` — docstring reconciled to what doctor now does
  - new `tests/test_plugin_install.py`; `.prawduct/change-log.md` entry
- **Tests:** unit — exact-path match, `user`- and `local`-scope, ancestor path NOT matching, symlink
  resolution, absent registry, five malformed-registry shapes, `CLAUDE_CONFIG_DIR` honored,
  read-only guarantee; integration — `--json` field, the human formatter in all three states, no
  exit-code change, the already-scaffolded re-run; prose — the anchor and both skills
- **Acceptance criteria:** full suite passes; `init-product` against a config home with no entry
  prints the exact `cd <target> && claude plugin install …` remedy and withholds the
  governance-activates promise
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** one commit after the review passes. The single `cumulative` review makes
the branch PR-ready; `/prawduct:pr` runs only when the user asks.
