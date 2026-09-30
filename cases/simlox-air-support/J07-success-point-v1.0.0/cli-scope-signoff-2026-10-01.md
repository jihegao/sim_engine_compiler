# J07.var04 success point before an abort: CLI scope sign-off (2026-10-01)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for a bounded fixed-seed `J07.var04` result comparison. This pair shows the global success factor counting two missions that pass a 75% threshold and then abort after aircraft failure. The native log classifies their success at the scheduled mission end, not as an event at the threshold. This is a bounded result-calculation claim, not completion of J07.

## Frozen source and one-field mechanism delta

The [full-completion control](full-completion-control-input.json) is byte-identical to accepted `D06.position_direct_cm.1.0.0`, SHA-256 `ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78`. The [early-point child](early-success-point-input.json), SHA-256 `8117e6f073104b61fe59a52790d22bcf05b85132e75f1bc5d260652dcf67c1be`, changes `MissionType.BASIC-MISSION.MSUCPT` from `1` to `0.75` and changes the descriptive label. All 33 other tables, including the one aircraft, explicit position-A failure mode, local half-hour direct repair, 8/20/32-hour scheduled missions, two-hour duration, seed and 36-hour result window, are identical. The [exact diff](exact-diff.json) SHA-256 is `88ea8f9781fc0040f2c482ea342083984bc0e0d7b62ba246e67227fc559807d0`; the pre-run [contract](contract.json) SHA-256 is `774c76eba8d0d3c1960c55e94e18de5c0c889857f72da900f27fddda0ed249ed`.

The installed SIMLOX manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical PDF page 265, defines `MSUCPT` as a 0–1 mission-length fraction used in result calculation with no direct simulation effect; physical pages 551–553 define the global result factors. The installed dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0` identifies `MissionType.MSUCPT`. The installed `Simlox.exe` SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`. Proprietary sources and raw native models are retained locally.

## Sealed native pair

Two fresh, sequential session-0 SSH runs used the host-wide `Global\SimloxIssue18NativeQueue` mutex, guarded GUI PID 13340/session 1 throughout, and performed import, export, calculation, JSON report and exact source-roundtrip checks. Each of the 18 row-containing source tables roundtripped exactly. Both input conversions had zero errors and inherited warning #108 because event logging is enabled. Each immutable local `runs/` closure seals its invocation, source and executable fingerprints, raw model, log, report and step SHA-256 hashes. Native JSON trailing commas are normalized only in parser copies.

| Variant / run ID | `invocation.json` SHA-256 | `closure.json` SHA-256 | `report-raw.json` SHA-256 | `model.log` SHA-256 |
| --- | --- | --- | --- | --- |
| `j07-full-success-control-v100-20261001-01` | `f1f8ae9a99d65e63c01dee52502b456027e215551256ce48640474b10246adb8` | `a3d9ba814261fc81e960456cf993681fc5fdb2a90e2485b4801360d477d25cc8` | `230403de72c36ae2ba2b6e57939ef9dd94571f94de840fa718084736e93630b8` | `92930370c7a60faa7870fa4fb43fffad73d2c3582e187c39506927012198ae1a` |
| `j07-early-success-v100-20261001-01` | `97102920026de5570473dcf265d9052e150bcb5423e8212ffe62a2eaae583565` | `400fad12f4a354a0372c3d826baa589bcf28f516c2549fb3f20025cf9e03d714` | `b6e6949e31df23663a20065a1b49cc4956f86b1f7db9a3c9b32f7a11d65524ae` | `7ee7dc0a3f093616fa5d57cfe8a3b06ee6b06bd597f322b4e563c473ec07a144` |

## Event and result ledger

Both runs start one-aircraft missions at 8, 20 and 32. The first and third suffer the same position-A critical failure at 9.8829 and 33.8602 and are logged as aborted. The middle mission succeeds and completes at 22. Each aborted mission is logged as `aborted mission completed` at its nominal end, 10 or 34. With `MSUCPT=0.75` and a two-hour mission length, the result threshold is 9.5 or 33.5, before the corresponding failure; with `MSUCPT=1`, the threshold is the nominal end, after the failure. The child log emits `mission success` at 10 and 34 for those aborted missions, and the control log does not. These logged timestamps do not show a success event at 9.5 or 33.5.

| Run | Planned / started missions | Aborted after failure | Native successful-mission classifications | `MTMF` | `MSTF` | `MSUF` | `STMF` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full-completion control | 3 / 3 | 2 | 1 | 1 | 1 | 0.3333333433 | 1 |
| 75% success point | 3 / 3 | 2 | 3 | 1 | 1 | 1 | 1 |

The `ResultSummary` rows differ only in `MSUF`. Both 72-bin `SystemResults` and `StockTotalResults` tables are byte-equivalent after JSON parsing. The System intervals integrate to 26 ready, 9 assigned, 6 operating and 1 direct-repair aircraft-hour in each run; `NFAIL=2` and `NREPT=2` are interval event-count totals, not hours. All 72 Stock rows have `PNB=1` and zero demand/backorder quantities. In the final 35.5–36 System bin the aircraft is ready, with zero assigned, operating, repairing or failed state. The native event streams are identical after removing the two additional mission-success lines and their corresponding arrival annotations.

The [author validator](validate.py) SHA-256 `7b88ab69765cdd8db2b91f34a6f3450c0031bac7e6318fd9ea2af663ccc78fe6` passes [32/32 checks](review/author-validation-2026-10-01.json), report SHA-256 `50ad91b9d8991b565446fecf2716f9284ee8a7fac56422eff055eb4c28e89656`.

A separately written [independent read-only verifier](review/independent_readonly.py) SHA-256 `b39f4a19a007325eff424bf21f00deb98e1146c369b9e1dfcd911fdfdf4e6956` passes [49/49 checks](review/independent-readonly-2026-10-01.json), report SHA-256 `7fa008f001d76537b19168abe2ea4bd8ee37adbaf1002a09ad60ebb9ca23b337`. It replays the raw closures, exact input delta, event stream, all System and Stock bins, summary and terminal state without importing the author validator or calling SIMLOX. Its `bounded_go` explicitly excludes a threshold-time event claim.

## Limits

The result is a fixed-seed pair with two native stochastic failure times and one direct-repair route. It does not show a success event at the threshold itself. The CLI JSON report has a global `ResultSummary` but no separate per-mission table in this setup; the individual classification is reconstructed from mission-identity log lines and the paired global factor. Partial formation success `J07.var03`, unit/group/type aggregation `J07.var05`, regenerative denominator exclusion, other failure times, GUI display and cross-engine behavior remain unverified. Issue #18 remains open.
