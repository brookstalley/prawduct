---
name: ping
description: Trivial liveness check for the Prawduct plugin — confirms the plugin loaded and skills resolve under the /prawduct:* namespace. Manual-only; type /prawduct:ping to verify a plugin install.
user-invocable: true
disable-model-invocation: true
---

This skill exists only to prove that plugin skills resolve under the
`/prawduct:ping` namespace (Chunk 1, v2.0.0 plugin distribution). It performs no
file access and changes no state.

Respond with exactly this, and nothing else:

```
prawduct plugin: pong
```

If the session-start banner showed a version (e.g. `Prawduct v1.8.1 (plugin)`),
add a second line echoing that version. Otherwise omit the second line.

Echo the banner's parenthesised part **verbatim**, including any load-provenance
segment (`Prawduct v3.1.0 (plugin · develop@a1b2c3d+dirty)`). That segment names
which checkout is actually loaded, which is the whole reason someone pings — a
managed install never prints one, so dropping or normalising it would answer the
question wrongly.
