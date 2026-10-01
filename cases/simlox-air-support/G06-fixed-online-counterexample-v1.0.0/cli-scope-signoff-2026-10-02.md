# G06.var04 fixed online-repair CLI scope sign-off — 2026-10-02

**Decision:** Accept a bounded native fixed-mission negative case after author and independent replay. Publish `G06.var04` only for the direct-CM passive B/A/C configuration in this package. Issue #18 remains open.

## Frozen source and runs

- Accepted continuous `ONLM=Y` parent: `G05-unavailable-standby-v1.0.3/unavailable-input.json`, SHA-256 `b0d79caeb71dbf991291b9122dff3139bc52c27e2c014b5bf624632539101f0d`, run `g05-unavailable-v103-ssh-20261002-01`.
- Fixed `ONLM=Y`: `fixed-input.json`, SHA-256 `ce407655c86e0af85460ba30d32eb28ffc93f54c1acc68bbf4d6fcbee79e723b`, run `g06-fixed-y-v100-ssh-20261002-01`.
- Fixed `ONLM=N`: `fixed-deferred-input.json`, SHA-256 `06a3cb45320c90f4a90027f562c17e86be46b25bd62b9106b1f6ab0cbcc99aa8`, run `g06-fixed-n-v100-ssh-20261002-01`.
- `exact-diff.json` SHA-256 `9d7a6b6212fb05f1ca2c0fd7001eaa7f4a6cb3591b358697046f109e296d91c3`: parent→fixed Y changes MissionType and PDESC; fixed Y→N changes only ONLM and PDESC.

## Native result

All three runs have sealed session-0 SSH invocations, the host-wide native mutex, GUI PID13340 preserved, five completed exit-zero steps, exact 23 populated-table import/export roundtrips, converter Errors: 0, and 72 aligned half-hour System and Stock bins. The only converter warning is #108, indicating the enabled simulation log may be extensive.

Fixed Y and N have byte-identical event logs: B fails h8.94145, B→A completes h9.44145; A fails h17.5636, A→C completes h18.0636; mission success and completion h34. Neither arm starts CM during the mission. Both start B's 40-hour and A's half-hour direct CM at return h34, finish A at h34.5, and leave B open at horizon36. ResultSummary and every System/Stock report cell are identical across the fixed arms.

The accepted continuous Y parent has the same fault/switch/mission event times, but starts B/A CM at failure h8.94145/h17.5636 and finishes A h18.0636. `SystemResults.NREPT` moves from [18,18.5) to [34.5,35) in fixed. Continuous ResultSummary `MSTF/MSUF=0/0`; fixed `1/1`. These pattern-dependent fields are not substituted for the explicit mission-success event. All Stock cells match across the three runs.

## Acceptance limits

The fixed Y/N pair directly isolates ONLM and demonstrates that enabling it did not initiate in-mission direct CM in this one fixed-mission model. Continuous versus fixed changes `MPAT` and the required `TFOUT/TFRET` travel fractions together; it is contextual evidence, not an isolated MPAT effect. No physical item replacement, resource demand, locality, shortage, whole-block failure, other seed, GUI-only behavior or cross-engine parity is claimed. The catalog's wider G06 case remains incomplete.

Author validation: `author-validation.json`, 37/37 checks. Independent read-only verdict and SHA-sealed raw evidence are indexed by `evidence-index.json`.
