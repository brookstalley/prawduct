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
