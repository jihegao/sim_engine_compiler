# Development boundaries

- Read README.md, docs/architecture.md, docs/semantic-baseline.md and docs/roadmap.md before implementation. The Python reference runtime is executable and is the accepted semantic baseline; Rust remains a scaffold.
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

## Model and engine boundary review

- Models compose rules through IR; the engine provides reusable operations with explicit semantics. New cases may justify engine extensions, but must not turn the generic runtime into a catalogue of whole-model implementations or introduce dispatch by case/model name.
- Before adding an operation, check whether existing IR operations can express the required behavior. In the PR, identify the missing semantics, justify the smallest necessary extension, and separate model rules and domain lowering from reusable compiler/runtime changes. Code location in the engine repository is not evidence of generality.
- Define an operation's inputs/outputs, preconditions, state reads/writes, time and ordering behavior, random requests, termination/resource limits, and backend support. Express configurable model parameters, thresholds, and bounds in validated IR rather than hard-coding benchmark values in the generic runtime.
- Restricted, versioned domain/profile operations remain allowed for compatibility where decomposition is not yet supported. Register their capabilities explicitly, document fixed assumptions and supported ranges, and reject unsupported configurations. Classify them as restricted operations, not general engine primitives; moving an entire case behind an operation name does not establish reuse.
- Support a reusable-operation claim with executable contract tests independent of the motivating model's name and fixture, including at least two distinct IR compositions or configurations within the declared range. Keep source-model/oracle acceptance separate from these reuse checks, and preserve the affected profiles' Python/Rust semantic regressions. A passing case alone proves neither generality nor cross-domain applicability.
- Review each new case against this boundary: can its rules be changed or composed within the declared capability range by changing IR/domain definitions without rewriting the generic runtime? If not, identify and classify the remaining capability gap instead of copying the case's rules into another runtime implementation. No speculative universal IR or immediate rewrite of existing compatibility operations is required.
