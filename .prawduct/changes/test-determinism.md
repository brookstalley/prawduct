---
schema: 1
type: feature
scope: test-determinism
date: 2026-11-24
title: Test determinism and dependency scope (#1243)
---

The test regime learns eight patterns that make a test's result unrepeatable, or unusable by an
incremental runner: a root conftest importing the app, an autouse fixture or package `__init__`
that imports everything, fakes or import-time code reading the real clock or randomness, build
output or tool state inside the checkout, whole-repo scans at collection time, and writes into the
checkout from shared test code. They are catalogued in one doc. A static detector checks changed
files at review: a change that newly introduces either of the first two is blocking at the merge
boundary, and the fake and import-time clock reads are warnings. `/prawduct:doctor` and onboard list
the existing sites.

## Consumer note

A boundary review now blocks a change that adds a first-party module-level import to a root
`conftest.py`, an autouse fixture that imports first-party code, or a package `__init__.py` that
imports every submodule. A deliberate case is waived on its line with
`prawduct:allow prawduct/test-scope -- reason`. Existing sites don't block; `/prawduct:doctor` lists
them.
