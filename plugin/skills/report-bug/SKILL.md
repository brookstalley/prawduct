---
description: File a bug report about PRAWDUCT ITSELF (its skills, hooks, gates, or methodology — not a bug in this product) as an issue on prawduct's own public tracker. Recomposes the report in prawduct's terms, shows you the exact bytes that would leave this repo, and sends nothing without your approval of them. Use when a prawduct gate/skill/hook misbehaves while you work in a product repo.
argument-hint: "[short description of the prawduct bug]"
user-invocable: true
disable-model-invocation: false
---

You are filing a bug report about **prawduct itself** — a defect in its skills,
hooks, gates, `prawduct-hook` subcommands, `lib/`, or methodology — discovered
while working in a product repo that prawduct governs.

The report leaves this repository. It becomes a **public GitHub issue in someone
else's project**, and that write does not come back: GitHub has no issue-delete
and never reuses a number. So this skill has two jobs of equal weight — get the
bug reported, and make sure nothing of this product's goes with it.

Two things carry that, and neither is optional:

- **You recompose the report in prawduct's terms** (step 2). No product name, no
  paths, no ids, no domain vocabulary. This is your judgment and nothing checks
  it mechanically — there is no redactor, and this skill does not pretend there is.
- **A human reads the exact outbound bytes and approves them** (step 4). Not a
  summary of them. The approval is a digest of the payload, and the adapter
  re-renders and re-computes it at send, so what was approved is what is sent.

Never let this skill error.

## 1. Confirm the bug is in prawduct, not in this product

Before anything else, decide: is the defect in **prawduct's own machinery**
(a `/prawduct:*` skill, a Stop/SessionStart gate, a `prawduct-hook` subcommand,
`lib/`, a methodology guide), or in **this product's** code/specs/backlog?

- **Product bug** → STOP. This is the wrong channel. File it in the product's own
  backlog (`/prawduct:backlog add`) and file nothing upstream.
- **Prawduct bug** → continue.

If you're unsure, say which way you're leaning and why, and ask the user to
confirm before filing.

**In the prawduct checkout itself, this skill is also the wrong channel.** A bug
in prawduct found while working *on* prawduct is ordinary backlog work —
`/prawduct:backlog add`. The adapter refuses a self-filing on its own (`self-file`),
so you will be told; you can just skip the round trip.

## 2. Recompose the report in prawduct's terms

Write the report **from scratch, in prawduct's vocabulary** — do not paste,
summarize, or lightly edit what you saw. Two modes:

- **Synthesize** *(simple, reproducible bugs)* — write a minimal generic
  reproduction: a few lines that trigger the prawduct defect against a bare
  fixture, standing alone with no product content in them.
- **Abstract** *(diagnostic bugs — the common case)* — describe the scenario with
  generic placeholders for every particular: "a governed repo with a feature
  branch", "a skill file", "a backlog item id", "a merge to the default branch".
  Never the real branch, path, id, product name, or domain term.

**Never crosses, in either mode:** the product's or repo's name, filesystem
paths, internal ids, learnings prose, domain vocabulary, and verbatim code
excerpts unless you synthesized them yourself and the user confirms it at step 4.

Then compose the three inputs the adapter takes:

- **component** — the prawduct surface at fault, in prawduct's own names:
  a skill (`critic`, `pr`, `backlog`, …), `prawduct-hook <subcommand>`,
  `lib/<module>`, a methodology guide, or a Stop/SessionStart gate. One line,
  never a product-side name.
- **title** — the **symptom alone**, one line, no prefix. The adapter renders
  `[prawduct] <component>: <symptom>` itself, and the whole rendered title must
  fit the issue standard's §1 rules — so keep the symptom short enough that the
  composed line does. The preview tells you if it doesn't.
- **body** — these sections, and only these:

  ```
  ### Problem

  The symptom and its observable effect. Lead with what went wrong, not the
  suspected cause.

  ### Reproduction

  The synthesized repro, or the abstracted scenario.

  ### Expected

  What prawduct should have done instead.

  ### Root cause

  Optional. The mechanism if you traced it, marked verified-vs-inferred
  (Principle 5 — Honest Confidence). Omit the section if you only have symptoms.
  ```

**Do not write a `Component` or `Found in` section** — the adapter composes both,
and it *sources* the version from the running manifest rather than recalling one.
That is why it is not your step: a recalled version drifts as the plugin updates.

**Do not put a ```` ```prawduct ```` fence anywhere in the body or component.**
It is refused outright, because a second parseable block would fold into the
provenance block permanently on the receiving side. A report that needs to *show*
one indents it instead.

**Write the body to a scratch file, once.** You will pass the identical bytes to
two commands, and the second one is matched against a digest of the first — so
retyping the body between them is how a filing refuses with `approval-mismatch`
for no reason a reader can see:

```
prawduct-hook backlog file-upstream \
  --component "<surface>" --title "<symptom>" --body "$(cat <scratch>/report.md)"
```

## 3. Preview the exact outbound payload

Run the command above **without** `--approve`. It sends nothing — the preview arm
is never handed a transport at all — and prints the whole payload verbatim: the
target repo, the rendered title, every byte of the body, and a `payload-digest`.

**Read the warnings before you read the payload.** A `filing would refuse (…)`
line means the send cannot succeed until you fix what it names, and fixing it now
costs one recomposition instead of a wasted human review:

- `filing-disabled` — this product's `Upstream filing` preference is
  `never-file`. That is a standing no and the adapter honors it without
  exception. Go to step 6; do not ask the user to override it.
- `self-file` — you are in prawduct's own checkout. See step 1.
- a title refusal — the composed title breaks an issue-standard §1 rule.
  Shorten the symptom and preview again. Fix this *before* step 4: upstream, a
  non-collaborator filer cannot retitle afterwards.

`lint:` findings are advisory budget hints. They never block a filing. Fix them
if the payload is genuinely bloated; ignore them otherwise.

## 4. Show the user the payload and get an explicit approval

Show the user the **exact bytes the preview printed** — not a summary, not a
description of them. Approval given to a summary is not approval of what gets
sent, which is the whole reason the preview prints verbatim.

Ask them to approve, and ask them plainly to check for anything of theirs in it:
a path, an id, a name, a turn of phrase out of their domain.

**If the payload contains a code block, ask a second, separate question:** is this
code synthetic and non-proprietary? A code block is the leak vector that survives
recomposition most easily, so it gets its own confirmation rather than riding
along inside a general "looks fine".

**If no human is present, stop here and file nothing.** Under `ask-user` — the
default — an unattended session's answer is "don't file", never "file anyway".
Say the report is composed and waiting for a person. Do not supply the approval
token yourself: the adapter cannot tell a fabricated approval from a real one,
and that limit is exactly why this obligation is written down.

Where the product's preference is `always-file`, the user has already given
standing consent and this step's asking is waived — your recomposition in step 2
is then the only thing between their session and a public issue, so hold it to a
higher bar, not a lower one.

## 5. Send

Repeat the command with the digest the preview printed, and **the same
`--component`, `--title` and `--body`**:

```
prawduct-hook backlog file-upstream \
  --component "<surface>" --title "<symptom>" --body "$(cat <scratch>/report.md)" \
  --approve sha256:<the digest from step 3>
```

The adapter re-renders the payload from those flags, recomputes the digest, and
refuses unless it matches — that is what makes "sent is what was previewed" a
property of the bytes rather than a claim of yours.

On success it prints the issue URL. Give the user that URL.

**Every refusal files nothing** — that is the guarantee worth stating when you
report one, because a caller's instinct is to wonder what got half-written.
Nothing did. A refusal you did not already predict at step 3 is one of:

- `auth` — no `gh` identity resolved. A filing is never anonymous. Go to step 6.
- `approval-mismatch` — the payload flags changed between the two calls. Preview
  again, show the user the new bytes, get a fresh approval. Do not hunt for the
  old digest.
- `target-not-pinned` — only reachable if a `--repo` was passed. Don't pass one.

The full refusal set and its rationale live in
`documentation/backlog-service-upstream-filing.md` §5. Read them there rather
than from a copy.

## 6. When there is no reachable path

The preference says `never-file`, or no `gh` identity resolves, or the send
cannot complete. Then:

**File nothing, anywhere.** In particular, do **not** capture the bug in this
product's backlog as a substitute. An upstream bug parked in a product's backlog
helps nobody — the people who could fix it never see it, and it clutters a
backlog whose triage cost is real. Submit or nothing.

Tell the user what stopped it and point them at the tracker so they can file it
by hand if they want to — the recomposed report from step 2 is right there in the
transcript for them to paste:

**https://github.com/brookstalley/prawduct/issues**

That's it — nothing fails, and nothing was written.

## What is and is not guaranteed here

Worth being straight about, because a reader deciding whether to trust this
channel deserves the real shape of it:

- **Mechanically guaranteed.** The target is a plugin constant, not anything a
  caller can name. Nothing sends without an approval token. The token is matched
  against a re-render of the bytes. A filing is never anonymous. Prawduct's own
  repo can never file to itself. `never-file` is a hard refusal in every case.
- **Not mechanical, and carried by this skill instead.** That the report contains
  no product content (step 2), that a human actually read the bytes (step 4), and
  that a human was present at all. The adapter cannot detect attendance; the
  owner chose that trade knowingly over a stricter attendance gate
  (`documentation/backlog-service-upstream-filing.md` §4.3).

## Receiving side — triage (when you ARE in the prawduct repo)

The other end of the channel. New reports arrive as **issues** on prawduct's own
tracker, carrying the `[prawduct]` title prefix and no labels — a non-collaborator
filer cannot set them, so triage applies the taxonomy on arrival.

A local `incoming-bugs/` drop-box also still exists, holding reports filed before
this channel moved to issues. Nothing writes to it any more. While it has
untriaged reports, the `untriaged-upstream-reports` session-start advisory
surfaces a count and points here. To triage one:

1. Read each report in `incoming-bugs/`.
2. For each, capture the durable record in the committed backlog:
   `/prawduct:backlog add` (set a real `area:`, and `refs:` the report if useful).
   The backlog item — not the gitignored report — is what survives.
3. **Archive** the processed report: move it to `incoming-bugs/archive/`. The
   advisory counts only top-level `*.md`, so archiving clears each report from the
   nudge while keeping it locally for reference (git tracks neither — the drop-box
   is gitignored; the backlog item is the record). `archive/` is reference-only —
   prune it whenever it gets noisy; nothing depends on it.
