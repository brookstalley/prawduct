<!-- The DROP-BOX report format. Nothing writes this any more: `/prawduct:report-bug`
     files upstream as a GitHub issue, and its payload is composed from
     `documentation/backlog-service-upstream-filing.md` §2 — not from this file.

     Do NOT use this as the shape of an upstream filing. Three of its fields are
     exactly what must not cross an owner boundary: `Reporter`, `used from the
     <product> repo`, and a `## Context` section that asks for the host repo's
     particulars. They were safe when the report stayed on one machine.

     Kept because reports already written in this shape are still sitting in
     `incoming-bugs/` waiting to be triaged, and this is what they look like. It
     retires with the drop-box. -->

# <one-line title: the bug, stated as a symptom>

- **Severity:** <low | medium | high> — <one phrase on impact / how much friction>
- **Component:** <the prawduct surface(s): a skill (`critic`/`pr`/`backlog`/…), `prawduct-hook` (subcommand), `lib/<module>`, a methodology guide, a Stop/SessionStart gate>
- **Reported:** <YYYY-MM-DD>
- **Found in:** prawduct <vX.Y.Z> (plugin), used from the <product> repo
- **Reporter:** <who / what session filed this>

## Summary

<2–4 sentences: what is wrong and the observable effect on the session or user.
Lead with the symptom, not the suspected cause.>

## Context

<What you were doing when you hit it; the host repo's relevant setup (gitflow vs.
trunk, worktrees, custom preferences) — anything that shaped the failure.>

## Symptoms

<Concrete and specific. Number them if there are several. Quote exact command
output, gate messages, or stderr where you have it.>

## Root cause (if known)

<The mechanism, with `file:line` if you traced it. Optional — omit the heading if
you only have symptoms. Honest confidence: mark what is verified vs. inferred.>

## Suggested fix (optional)

<The shape of a fix if you have one — not a patch, just the direction. Omit if
you don't.>
