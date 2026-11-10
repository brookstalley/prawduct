---
schema: 1
type: chore
scope: release-v3.8.1
date: 2026-11-10
title: v3.8.1 is cut, and develop reopens on 3.8.2-dev
---
v3.8.1 was promoted as a whole-develop release: all 5 pending scopes shipped and none were
withheld (`.prawduct/artifacts/release-plan-v3.8.1.md`). This commit reopens `develop` with the
three version files on `3.8.2-dev`, a low guess: if the fragment-only release (#1125) ships as
a minor, the next cut overwrites all three.

## Consumer note
none: release mechanics for v3.8.1, whose notes are already published
