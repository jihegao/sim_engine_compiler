# A11 mixed-type per-type minimum: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted` for the bounded paired `MissionSystem` behavior below; `reusable_published` after merge to `simlox/main`. Explicit formations and the rest of A11 remain unverified under Issue #18.

## Source and lineage

The published A03 1.0.1 parent input SHA-256 is `d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`. The [untyped control](control-input.json) is `88f22f01e6984f34a4c9332be8a56ddd42268f6e33869bbd0a6938cad47f0e82`; the [per-type required input](required-input.json) is `4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213`. The [exact diff](exact-diff.json) SHA-256 is `a5fa9cc908ab242e8d4aa81256662ff5cba20df1fb0ca1455414005f46d6bca9`. Parent to control adds a second system type and deployment row and updates labels; control to required adds only a two-row `MissionSystem` table and description. The [contract](contract.json) SHA-256 is `a81ed8a414112e495cf99ca2b73e63c8c5793667479f495d73e54541440e7acd`.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Pages 184, 188, and 302–304 describe total versus per-system-type requirements. The proprietary manual remains local.

## Guarded native evidence

The final session-0 SSH queue runs are `a11-control-20260930-02` and `a11-required-20260930-02`, with closure SHA-256 values `21e9a0600ad24252ba7999ca59a348d5c5a3bf3b38fcf508ca804b7325a0b6a5` and `9961c598d976288284c58ef43afbb32ffc0aea547502d3177ffefd39404df08a`. Each closure seals 12 raw files and unchanged source hashes, including the corrected contract. The runner preserved GUI PID 13340 and held `Global\SimloxIssue18NativeQueue`. Both runs completed import, export, calculation, report, and source-row check with zero conversion errors. The only warnings were #108 (log) and #126 twice (both teaching systems have no items). All 13 control and 14 required populated source tables roundtrip exactly.

Both models begin with two A aircraft and one B aircraft ready. Zero-duration preparation start/end events occur at hour 7. The untyped total `MissionType.NOS=MNOS=2` control allocates and flies A instances 0 and 1. Adding `MissionSystem.NOS=MNOS=1` for each type changes the allocation and flight to A instance 0 and B instance 2. Both two-aircraft missions launch at hour 8, log success/return at hour 10, and produce four aircraft mission-hours across 72 half-hour system bins. All three aircraft are ready at the end. `MSTF`, `MSUF`, and `STMF` equal one. The paired difference supports type-specific minimum allocation in this exact ready-aircraft configuration; the report totals alone would not identify the aircraft types.

The [author validator](validate_native.py) SHA-256 is `c0a539075372afed10cd8ec5aaabf8f3843afea19b7101c8499d7b99519ff342`; its [saved replay](review/author-native-validation-2026-09-30.json) is `478dac4c4cc10d684b243ba92f1ad9c823071ef2799456fbbfe74f06fbe5a99f`. A [separate read-only reviewer](review/independent_mixed_type_readonly.py) SHA-256 `5ae00c3a209a877d881108e3c786511b2fc70cc1f864768398ba7ad5da08ff39` passes [56/56 checks](review/independent-mixed-type-2026-09-30.json), SHA-256 `2b6ead9fe7e1e793db75445c72e13a266a1a3f7b939f47aa761d926d3cc0e3dc`, without importing author validation. Earlier `-01` paired runs remain locally preserved but are excluded from this decision.

Raw native models, outputs, logs, and reports remain in ignored local `runs/`. Reproduce source with `python build.py` and `python describe_diff.py`; replay sealed evidence with `python validate_native.py` and `python review/independent_mixed_type_readonly.py`. New native runs require fresh run IDs and the pinned local environment.

This scope does not verify shortages, changing type readiness, preference order, `MNOSA`, explicit `Formation` alternatives, `ALOAA`, incomplete formations, failures, positive-duration preparation, resource competition, GUI-only behavior, or cross-engine parity. Issue #18 remains open.
