# B04 cross-midnight turnround: CLI scope signoff

**Decision:** `native_behavior_accepted` for the paired, deterministic one-aircraft behavior below; `reusable_published` after merge to `simlox/main`. This does not complete the full B04 catalog case or its variants.

The accepted parent is published B02 1.0.2 (input SHA-256 `fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34`); the A02 repeated-mission prerequisite is also published. Frozen `control-input.json` and `turnround-input.json` SHA-256 values are `9cc5c39a6d2d93b98c03fc0c483bf90963a76e67be6953444003f30bfa8dd98c` and `9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5`. The [exact source diff](exact-diff.json) SHA-256 is `b13bdadbeeda7c7a38bec265882eaee53e3d3d3546748a641f5d06d322942f17`; the frozen [contract](contract.json) SHA-256 is `d65cef9a589fef1234bc1d09c649c61af31190ea867c8d7c4a106aa43f1fb6ca`. Relative to B02, both inputs schedule waves at 21.5 and 24.75 hours with a one-hour second-wave delay allowance. Only the child adds one one-hour `MissionTurnround` row. The installed 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; printed pages 181–183 and 305–307 describe the relevant preparation and post-mission work.

Sealed session-0 SSH native runs `b04-v101-control-20260930-01` and `b04-v101-turnround-20260930-01` have closure SHA-256 `c1c99765128e22ed73cba808fe019f1b943f95596f8ffb79aff8033781d609d4` and `85d25bd8fa2a053639ca9a93b3bbdd78a5c04e3db9a5d826e27998d500f95ae1`. Both completed guarded import, export, calculation, JSON report and source roundtrip with the global Issue #18 mutex and GUI PID 13340/session 1 preserved. All 17/18 populated business source tables roundtripped exactly; conversion had zero errors and warnings #108/#126.

| Event | Control | One-hour turnround |
| --- | ---: | ---: |
| First preparation and mission | 20.5–21; 21.5–23.5 | 20.5–21; 21.5–23.5 |
| First post-flight turnround | Instantaneous markers at 23.5 | 23.5–24.5, crossing midnight |
| Second notice/preassignment | 23.75 | 23.75 |
| Second allocation and preparation | 23.75; 23.75–24.25 | 24.5; 24.5–25 |
| Second mission and completion | 24.75–26.75 | 25–27 |
| Second post-flight turnround | Instantaneous markers at 26.75 | 27–28 |

The same `<TEACH-AIR-01,0>` flies both missions in each run. Both missions succeed in both runs. The 72 half-hour system bins integrate to four aircraft mission-hours and one preparation hour in each; `NSYMT` integrates to zero versus two turnround hours. The 72 stock bins show no demand, movement or waiting, with one aircraft ready at the hour-36 end. The observed 0.25-hour second-launch shift follows release from turnround, rather than a stock or maintenance interruption. Internal scheduling order at the same timestamp is not directly exposed.

The [author validator](validate_native.py) SHA-256 is `c48ec0e36ec42fb8929c3e156a0adfec1d4fc738bb7072e3123dddd4c9d61866`, and its [passing report](review/author-native-validation-2026-09-30.json) SHA-256 is `4d13b9e096a4f827a9ad0acf48772c8b906edad38f56636ffefb9a1adaa24832`. The separate standard-library [read-only reviewer](review/independent_turnround_readonly.py) did not import the author implementation or invoke SIMLOX. Its script SHA-256 is `6f585f0e03c645a55b50b563d539124da276437c3e9a7126dcf88958e5012fbe`; its [72/72 passing report](review/independent-turnround-2026-09-30.json) SHA-256 is `a3bf505aa878a33f5da64f386d47c7930140bb1284da1200f94bc228a73e1b80`.

Raw native outputs remain in local ignored `runs/`. A prior local v1.0.0 probe retained the inherited 0.333333-hour second-wave allowance and cancelled that wave at 24.3333, before turnround ended at 24.5. It failed its predicted-success contract and is excluded. This signoff covers one aircraft/type, fixed durations and allowance, with no resource demand, repair or PM. Waiting turnround, exact day-boundary equality, arbitrary preparation overlap, GUI-only behavior and cross-engine parity remain unverified.
