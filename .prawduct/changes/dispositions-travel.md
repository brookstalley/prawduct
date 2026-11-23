---
schema: 1
type: fix
scope: dispositions-travel
date: 2026-11-23
title: "Dispositions travel between clones (#1207)"
closes: [brookstalley/prawduct#1207]
---
An ACCEPT, FILE or `--fixed` disposition recorded in one clone now reaches every clone that syncs
the branch, on the same notes transport as reviews and resolutions. Every clone picks the same
newest answer for a finding, ordered by the answer's sequence number rather than by store order.

## Consumer note
After `evidence sync`, another clone's census, briefing and reviewer prior-dispositions block show
answers recorded elsewhere. No gate reads a disposition, so nothing that travels lifts a gate.


