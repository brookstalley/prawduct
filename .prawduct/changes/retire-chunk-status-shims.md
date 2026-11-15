---
schema: 1
type: chore
scope: retire-chunk-status-shims
date: 2026-11-15
title: The three one-release chunk-status shims are retired
closes: [brookstalley/prawduct#1055]
---
Chunk-status shipped in v3.8.0 with three shims kept one release; v3.8.1 has released, so they go.

- `prawduct-hook critic-begin --chunk <id>` (the one-element alias of `--chunks`) is now a usage
  error (exit 1) naming `--chunks`.
- New review facts no longer carry the singular `chunk` (it was `chunks[0]`); they carry `chunks`
  and `chunks_proposed`. Facts already in a store keep their `chunk` and still read correctly, and
  the disposition census labels a review from `chunks` or the legacy `chunk`.
- `work_unit._live_declarations`, the pre-#1051 private name, is deleted (`live_declarations` is the
  public one).

`ledger-append --chunk` is a different command's flag and is unchanged.

## Consumer note

Replace `critic-begin --chunk 02` with `critic-begin --chunks 02` in any script or habit. A reader
of review facts should read `chunks` (falling back to `chunk` for facts written before v3.8.0).
