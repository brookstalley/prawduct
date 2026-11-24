---
schema: 1
type: fix
scope: yaml-inline-comment
date: 2026-11-24
title: project-state and plan readers drop an inline comment instead of keeping it in the value
closes: []
---
Owners annotate project-state lines. A product name written as `name: "acme"  # owner ruling …` was
read with its comment attached, so the product's telemetry label (the `project` field on every
ledger event, and the `stats` header) carried the comment. The product-name reader, the
`work_in_progress` readers and the build-plan frontmatter scalar reader (`branch:`, `scope:`) now
all take a value through core's one comment-then-quote pair. The frontmatter reader had the mirror
bug: it cut at the first `#`, so a branch like `fix/#123` read as `fix/`, and `plan bind` refused it
as unrepresentable. Such a branch now binds and reads back whole. The `work_in_progress` readers also
skip comment lines, so a comment on a branch-key line no longer stops the branch matching and an
indented comment no longer becomes a field; a column-0 comment ends neither `work_in_progress` nor
`product_identity`; and both readers treat `~` and any case of `null` as unset.

## Consumer note
A product whose `product_identity.name` line carries a trailing comment gets its proper label from
now on. Ledger events already written keep the label they were written with.
These readers now follow YAML's comment rule, like the rest of prawduct's readers: an unquoted ` #` starts
a comment. A `work_in_progress` description such as `description: fix #745 parsing` now reads as `fix`;
quote a value that contains ` #` (`description: "fix #745 parsing"`).
