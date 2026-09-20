# Development boundaries

- Read README.md, docs/architecture.md, docs/semantic-baseline.md and docs/roadmap.md before implementation. This repository currently contains a scaffold, not an executable simulation engine.
- Preserve the three layers: Business IR → Core Simulation IR → Execution Plan. Keep mutable RunState outside the plan.
- Import canonical simulation_inputs through integrations/spare_mvp. Do not create another Project JSON interpreter. Inspect the upstream revision and contracts before implementing the bridge.
- Keep aircraft rules in domains/aircraft_support. The compiler and generic runtime must not dispatch through `if domain == ...` branches.
- The Python reference runtime must execute the independent plan; do not subclass or instantiate the legacy model to supply its execution semantics. Legacy-model access belongs in isolated differential tooling.
- Unknown operations, unsupported profiles, invalid units/references, and backend capability gaps must produce explicit errors. Never silently drop model behavior or execute arbitrary Python expressions from IR.
- Changes to time ordering, RNG calls, quantity handling, reservations, or serial/parallel work policy are semantic changes unless equivalence is demonstrated.
- Preserve source mappings, stable business identities, version metadata and input fingerprints. Do not use dense indices as random-stream identities.
- Keep source snapshots/golden evidence separate from generated runs. Never copy local databases or claim synthetic fixtures reproduce an unavailable upstream benchmark.
- Report implemented, planned, verified and unverified capabilities separately. Documentation and scaffold checks are not simulation conformance tests.
- Add meaningful tests with executable behavior. Benchmark only after semantic acceptance, and separate compile, initialization, execution and end-to-end timing.
- Do not add a web UI, server, database, distributed scheduler, JIT, or running-world hot edits without a task requiring them.
