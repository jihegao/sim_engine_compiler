# B04: cross-midnight turnround and next mission

This bounded pair derives from published [B02 1.0.2](../B02-serial-preparation-v1.0.2/evidence-2026-09-29.md), whose input SHA-256 is `fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34`. The instructional A02 repeated-mission prerequisite is also published. The [exact diff](exact-diff.json) lists every change from B02 and between the two B04 inputs. Both schedule one aircraft on the same fixed mission type at hours 21.5 and 24.75; the second wave's allowed delay is one hour. The `turnround` input adds one `MissionTurnround` row with one hour of work after each return. The paired control has the same schedule and no turnround row.

Frozen input SHA-256: `control` `9cc5c39a6d2d93b98c03fc0c483bf90963a76e67be6953444003f30bfa8dd98c`; `turnround` `9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5`. The [contract](contract.json) was frozen before native runs. Each input completed guarded session-0 SSH import, export, calculation, JSON report and source roundtrip while GUI PID 13340 remained in session 1. All 17/18 populated business tables roundtripped exactly, conversion logged zero errors and only warnings #108/#126. Run IDs are `b04-v101-control-20260930-01` and `b04-v101-turnround-20260930-01`; raw closure SHA-256 values are `c1c99765128e22ed73cba808fe019f1b943f95596f8ffb79aff8033781d609d4` and `85d25bd8fa2a053639ca9a93b3bbdd78a5c04e3db9a5d826e27998d500f95ae1`. Raw evidence stays in ignored `runs/`.

| Event | No-turnround control | One-hour turnround |
|---|---:|---:|
| First mission preparation | 20.5–21 | 20.5–21 |
| First mission operation / completion | 21.5–23.5 | 21.5–23.5 |
| First post-flight turnround | 23.5 instantaneous markers | 23.5–24.5 |
| Second wave notice | 23.75 | 23.75; aircraft preassigned |
| Second aircraft allocation | 23.75 | 24.5, after turnround |
| Second mission preparation | 23.75–24.25 | 24.5–25 |
| Second mission operation / completion | 24.75–26.75 | 25–27 |
| Second post-flight turnround | 26.75 instantaneous markers | 27–28 |

The same `<TEACH-AIR-01,0>` flies both missions in each run. All missions log success and completion; neither run cancels or aborts. The 72 half-hour system bins integrate to four aircraft mission-hours and one hour of preparation in each run. `NSYMT` integrates to zero versus two turnround hours. Stock bins show no demand, movement or waiting. One aircraft is ready at the hour-36 end. The native log names actual turnround task start/end and post-turnround arrival/ready events; the no-turnround control still emits same-time turnround lifecycle markers, so those markers alone do not show positive work.

The installed 2017 manual (SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`) describes post-mission work and continued mission association on printed pages 183 and 305–307. The timeline establishes an observed cross-midnight delay and release ordering for this pair. A separately preserved local 1.0.0 candidate with the inherited 0.333333-hour delay allowance cancelled its second wave at 24.3333 before turnround ended; it did not satisfy its contract and is not part of this accepted pair.

Reproduce source with `python build.py` and `python describe_diff.py`; replay sealed evidence with `python validate_native.py` and the separate reviewer script. A fresh native run requires a new run ID through the session-0 SSH runner and global mutex. Resource-constrained turnround, waiting, day-boundary equality, repair after return, arbitrary preparation overlap, GUI-only behavior and cross-engine parity remain unverified.
