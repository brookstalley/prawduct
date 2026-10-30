# Scenario tests

Each scenario is an end-to-end evaluation: a product, a user persona with scripted answers, and a
rubric. Together they cover every structural characteristic, a range of risk levels and stacks,
and users from novice to deep expert.

| Scenario | Persona | Structural characteristics | Stack | Risk | Tests |
|----------|---------|----------------------------|-------|------|-------|
| **Quick To-Do App** | Mobile user (implied) | `has_human_interface` (mobile) | Mobile | Low | Light-touch process for trivial products; happy path |
| **Score Night** | Non-technical family user | `has_human_interface` (mobile) | Mobile | Low | Pacing for non-technical users; scope restraint |
| **DoseCheck** | Marketing manager | `handles_sensitive_data` (health), `has_human_interface` (iOS) | iOS / Swift | High | High risk at low scale; privacy without over-engineering |
| **Digest Bot** | Mid-level backend indie dev | `runs_unattended` (scheduled) | Python | Low-Med | Headless pipeline detection; no UI questions; external integrations |
| **Terminal Invaders** | Senior engineer | `has_human_interface` (terminal) | Any | Low-Med | Unusual UI substrate; real-time game loop; cross-platform terminal |
| **Chromavert** | Senior Rust engineer | `exposes_programmatic_interface` (REST) | Rust | Medium | API-only product; mathematical correctness; N×N conversion matrix |
| **QuickCheck** | Middle-school science teacher | `has_multiple_party_types`, `has_human_interface` (web) | Web | Medium | Multi-party workflows; trust boundaries; COPPA; non-technical vocabulary |
| **ThermoGraph** | Retired electrical engineer | `multi_process_distributed`, `runs_unattended`, `has_human_interface`, `exposes_programmatic_interface` | Go | Low-Med | Four overlapping characteristics; process topology; expert in systems, novice in web |

Run one by opening the repo in Claude Code and naming the file:

```bash
claude --plugin-dir ./plugin --add-dir .
> let's run through tests/scenarios/home-environmental-monitor.md
```

The coordinating session spawns a second session that does the work without seeing the scenario
file, relays the scripted answers, then scores the result against the rubric. A run takes 3–15
minutes.
