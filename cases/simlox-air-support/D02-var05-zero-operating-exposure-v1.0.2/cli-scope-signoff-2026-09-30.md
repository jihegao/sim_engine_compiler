# D02.var05 zero-initiation OPHOURS control: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed 60-hour traditional OPHOURS control with three scheduled profile rows whose initiation quantities are zero. No mission or failure is observed. This is a bounded D02.var05 result, not a direct measurement of the internal OPHOURS counter or a general failure-clock algorithm.

## Parent, source and exact delta

The accepted [D02.var01 traditional LRU parent](../D02-var01-traditional-op-hours-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2`. The [child input](native-input.json) SHA-256 is `b82bfd03fc1b2fab3ab7a5ffb257f9b129793636eb2969475fb1792062232f44`. The [exact parent diff](parent-diff.json), SHA-256 `1b8a162cb724d86c126a44da4afec09ebffdca93c4279bc09b616eb53c9196f5`, changes only the description label and `OperationProfile.IQTY=1→0` on the three retained scheduled rows at hours 8, 20 and 52. The other 29 parent tables are unchanged. The unit's `Operations.PRID=BASIC-SCHEDULE` assignment remains valid. `System.FRT` and `Item.FRT` remain 300000 per million `OPHOURS`; seed 1, horizon 60, installed LRU, stock and repair settings remain fixed.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; installed dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. `OperationProfile.IQTY` permits a nonnegative integer. The proprietary manual and dictionary are not uploaded. The [source-bound contract](contract.json) declared the zero-initiation hypothesis and recorded the two prior probes before this run.

## Native run and observed result

Run ID `d02-var05-zero-op-v102-ssh-20260930-01` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` mutex and GUI PID 13340 identity guard. Import, export, calculation, report export and roundtrip checker all completed with exit code zero. All **18 row-containing source tables** roundtripped exactly, including three all-null placeholder rows; the sealed contract's phrase “populated source business tables” refers to this same checker set. Conversion had **zero errors and one warning**, #108 for event logging. No default operation profile was generated.

The native event log contains initial aircraft/stock setup and day boundaries at 0, 24 and 48 hours, but no mission ordered, created, activated, started, completed or aborted; no preparation or critical random failure; and only an initial `Next random failure will occur 1e+010` marker. The 120 half-hour `SystemResults` bins cover 0–60 hours with `NSYRY=1`, `NSYMO=0`, `NSYMA=0`, `NFAIL=0` and `NREPT=0` throughout. The 120 stock bins show no demand or backorder. `ResultSummary` has one repetition and a 0–60 reporting window, with zero mission/failure measures. The child has no observed operating exposure in this fixed run; its internal OPHOURS counter is not directly emitted.

| Accepted raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `99f4c784c816a0bbcf633440de5abf006aa5646802e30486a2391019e5b9ca6b` |
| `closure.json` | `2cfbeb852e4d78ae8c3e6df9b024bd25d6fbc582c943f5fda6dff008f5a503ac` |
| `model.log` | `71234f37459888a2f7bc40a61543f20bc3097253de4e55c1e5297a8ba7676cb0` |
| `report-raw.json` | `b37abf9d4453ab3a376038f79e75481cdeda4a3adf6377937bfe6c01493da252` |

Two earlier sealed native probes are retained as **unpublished** corrections. [v1.0.0](../D02-var05-zero-operating-exposure-v1.0.0/PROBE-ONLY.md) deleted profile rows but left the unit assignment, causing conversion error #77 for unknown `BASIC-SCHEDULE` and a 4-byte SXO; closure SHA-256 `0afdc95a96070b60af4effe18a2246609e087bf7c21a024ecf6c36541250e2b9`. [v1.0.1](../D02-var05-zero-operating-exposure-v1.0.1/PROBE-ONLY.md) deleted the assignment too; SIMLOX generated a default 60-hour mission at hour 0 and a failure at 1.8829, so it was not a zero-exposure control; closure SHA-256 `35800c4d3d1ce8dc82ad961f36e6358266c97a486a4988c12b5ca0fa79cc66ac`. Raw artifacts remain in ignored local `runs/` for all three attempts.

The [author validator](validate_zero.py), SHA-256 `b57772a963f3d0f3838b4ef7235771936540cd0d19c5a2923a1ba90adda46691`, passes [76/76 checks](review/author-zero-validation-2026-09-30.json), SHA-256 `1156445e6c33a5da50c3d1343e45820a9ee96b82a1c6312ac862ba2fae04209b`. A separate reviewer wrote a [read-only replay](review/independent_zero_readonly.py), SHA-256 `8a3ac0f22d83ce8bd26387f5c76d8dbee795e433d3e8ac3431d5a25fbf96c82a`, without importing the author validator. Its [140/140 result](review/independent-zero-2026-09-30.json), SHA-256 `5538310216dbfcd495f589837caac677b05628cce2bc52bb45959352646a2e71`, independently verifies the accepted source/diff/raw seals, guard, conversion, log and report, and both failed-probe dispositions.

This result is specific to installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`, one seed and a zero-initiation scheduled profile. It does not test active missions with zero utilization, other seeds, idle PM or repair, GUI visual content or cross-engine equivalence. Issue #18 remains open.
