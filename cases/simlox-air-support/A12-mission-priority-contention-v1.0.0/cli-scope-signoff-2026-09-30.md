# A12 simultaneous priority contention: CLI scope signoff

**Decision:** `native_behavior_accepted` for the deterministic two-mission priority reversal below; `reusable_published` after merge to `simlox/main`. The full A12 catalog method and its variants remain unverified.

The accepted model parent is published A11 mixed-type minimum, input SHA-256 `4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213`. Published B01 fixed preparation supplied the positive 0.5-hour recipe (source SHA-256 `2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b`); B04 turnround is an accepted instructional prerequisite, not exercised as positive-duration work in this pair. Frozen `basic-high` / `second-high` input SHA-256 values are `300f3129b1f5d78018ad00875b545ffc1d7619dde5c3086c7a8bf0abb145094a` / `84e6a73b74502d259588e38ef43415d4e9c2d2f29307622a0fdd5e4c5d2c5135`. The [exact source diff](exact-diff.json) SHA-256 is `44a80825d808f20927cf796f0aef006dec6a199454cd65d25ca3f72a99f81b12`, and the pre-run [contract](contract.json) SHA-256 is `df5430701f6db9a63f44057985e0a8cd925b5bafb359ed0c831406e55375b480`. Apart from descriptive text, the pair changes only the two `MissionType.PRI` values, 1↔2. Both inputs contain 16 populated source tables.

The installed 2017 SIMLOX manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Printed pages 184–188 and 266 describe priority, typed minimums, partial allocation and the latest preparation-start calculation; pages 270–273 permit two same-time `OperationProfile` rows; pages 302–304 describe `MissionSystem`. The two profile rows have different `SPRID` mission IDs. Their concurrent calls and priority order were verified from the native log.

Sealed session-0 SSH native run IDs `a12-basic-high-20260930-01` and `a12-second-high-20260930-01` have closure SHA-256 `f6030bb8a0615cd0d1fa55e0566ab61d9ea3bc19a8bd75ff94d784afd7636ec8` and `430a6e43449afbba84d06d35565d5c444617b995576944f78d468b1541c3ad24`. Each completed import, export, calculation, JSON report and exact 16-table source roundtrip. Conversion logged zero errors, warning #108 (enabled event log) and two #126 warnings (teaching system types contain no items). The host-wide mutex and GUI PID 13340/session 1 were preserved; product `main` was untouched. Raw native files remain local in ignored `runs/`.

| Observation | `basic-high` | `second-high` |
| --- | --- | --- |
| Priority-1 mission, called at 7 | BASIC-MISSION | SECOND-MISSION |
| Priority-1 aircraft allocated at 7 | A#0 + B#2 | A#0 + B#2 |
| Priority-2 mission, called at 7 | SECOND-MISSION | BASIC-MISSION |
| Priority-2 partial allocation | A#1 | A#1 |
| Preparation | All three aircraft 7–7.5 | All three aircraft 7–7.5 |
| Priority-2 outcome | Waits, cancels at 7.83333; A#1 ready again | Same physical outcome |
| Priority-1 outcome | Launch 8, success/return 10 | Launch 8, success/return 10 |

The lower-priority mission **does prepare its spare A aircraft**. The contract's first hypothesis identifies the only *complete A+B pair* and winning launch; it must not be read as excluding this partial preparation. The observed cancellation at 7.83333 is consistent with the documented latest preparation-start calculation `8 + 0.333333 - 0.5`; this pair does not establish a general cancellation-time rule.

Each raw report has 72 half-hour system and stock bins. Event-derived `NSYRY`, `NSYMA`, `NSYMP`, `NSYMR`, `NSYMO`, `NSYA`, `STREQ`, `STACC` and `FTMO` reconcile bin by bin. The pair has 1.5 preparation aircraft-hours, four mission aircraft-hours, three preparation starts and successes, and `MTMF=MSTF=MSUF=STMF=0.5` for one successful mission of two called. There are no observed failures, PM or stock demands; all three aircraft are ready at hour 36. The author [validator](validate_native.py) SHA-256 is `c77bd72690b5c44e6cec5424c9a5726e4a7ff00b6fcf4087f9ff4abcf3b7e8da`, and its [passing report](review/author-native-validation-2026-09-30.json) SHA-256 is `7d8b1c9d05bdd1d98de46e4832f1cbd5375e3f0219f53d48ba7602d7341461b0`. A separate standalone [read-only reviewer](review/independent_priority_readonly.py) did not import author scripts or invoke SIMLOX; script SHA-256 `cefd3f77f3ec49b6febc60b59fc8643c38169b3c8fee518a6a31102a78bb2455`, [107/107 passing report](review/independent-priority-2026-09-30.json) SHA-256 `27c45312c03a813811712d7411d3bd2c23698a5884cfcafb95c3d70c85d8aa67`.

Rebuild with `python build.py` and `python describe_diff.py`; replay the sealed runs with `python validate_native.py` and the independent reviewer. A fresh native run requires unique run IDs, guarded session-0 SSH and the host mutex. Equal-priority ties, ready versus soon-ready selection, confiscation from an actively preparing lower-priority mission, resource waiting, failures/PM, changed schedules, GUI-only behavior and cross-engine parity remain unverified.
