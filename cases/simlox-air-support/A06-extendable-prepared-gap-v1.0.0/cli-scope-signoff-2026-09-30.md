# A06 extendable mission with two finite suspensions: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed `MPAT=EXTENDABLE` four-active-hour mission with two observed half-hour suspensions. The mission starts at hour 8 and completes at hour 13, so one hour of suspension extends its five-hour calendar span. This accepts only the tested configuration and observed run.

## Source and exact delta

The accepted [A05 prepared-replacement parent](../A05-var02-prepared-spare-probe-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d`. The [A06 input](native-input.json) SHA-256 is `5b53aa2cbaacb283e15bb7e7852afba215ec7fe5961434c3c2ce6f06768125c7`. The [exact diff](exact-diff.json) SHA-256 is `0d3acc9805be562792e834819a9cb12fb32e6a154299cf1e9b8d441bbb3aa34a`: `MissionType.MPAT` changes `CONTINUOUS→EXTENDABLE`, and `ProblemDescription.PDESC` changes a label; 29 other source tables are identical. `NOS=MNOS=2`, three deployed aircraft, fixed half-hour preparation, system failure rate and direct repair, seed, hour-8 start, `DURN=4`, and hour-16 report horizon stay unchanged. The [contract](contract.json) SHA-256 `3027f854fc294429758d0b3c29c172bbb3275dd2ca7483b9bb1b56a5856a0b35` predeclared the comparison and acceptance conditions.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Physical PDF pages 179, 182–183 and 265–266 distinguish extendable completion after requested active mission time from continuous completion at fixed calendar time; they describe suspension while below the minimum. The installed dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. Neither proprietary file is uploaded.

## Sealed native result

Run `a06-extendable-prepared-gap-v100-ssh-20260930-01` used session-0 SSH with an `sshd.exe` ancestor, host-wide `Global\SimloxIssue18NativeQueue` mutex, and GUI PID 13340/session-1 identity guard. Import, export, calculation, report, and exact source roundtrip checker exited zero. All 16 row-containing source tables roundtripped exactly. Conversion errors were zero; warning #108 enables event logging and #126 denotes the teaching system without items. The native JSON writer's trailing commas are normalized only in a parser copy, with raw byte hashes retained.

| Raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `e524f3c81184c80b1f67279766fbf43bf4bf8d59b8dd753dd61124b4854458cb` |
| `closure.json` | `766fb2a3c7a3d026998f86795fdbb91ba8f824074dcc8d393c55d644d9118ab5` |
| `model.log` | `55164fba5af8523e77679b49462a7ea45cb3655694891c1935a0d7c4c0384fae` |
| `report-raw.json` | `c17c86237fa97a08f03c814c63aa4bbaf406021bcaeccac09431892782a32064` |

Aircraft #0 and #1 prepare 7–7.5 and start the mission at 8. #0 incurs a critical random system failure at **9.8829**, leaving #1 attached and suspending the mission. Ready #2 prepares 9.8829–10.3829, while #0 receives direct repair. #2 attaches and the mission resumes at **10.3829**. #1 fails at **12.2431**, leaving #2 attached during a second suspension. Repaired #0 prepares 12.2431–12.7431, while #1 receives direct repair. #0 attaches and the mission resumes at **12.7431**; #2/#0 complete at **13**. The accepted continuous parent shares the first 9.8829–10.3829 interruption but stops at its fixed hour-12 end. The second failure in A06 occurs after that parent ended; random streams beyond the shared interval are not presumed identical.

The 32 aligned half-hour report bins cover hours 0–16 and integrate **eight aircraft mission-hours** (`NSYMO=STACC`), **one suspended aircraft-hour** (`NSYMS` from one retained aircraft across two half-hour gaps), **one repair aircraft-hour** (`NSYRP`), and **two preparation aircraft-hours** (`NSYMP`). There are two failures and repairs, four preparation starts/completions, zero stock demand/backorder, and three ready aircraft at the end. `MTMF=STMF=1` reflects four active mission hours at desired two-aircraft strength. `MSTF=MSUF=0` are fixed-mission-only measures and do not contradict the event success marker for this extendable mission.

The [author validator](validate_extendable.py), SHA-256 `ba5febc2bff1261a1b620c088d9aac8a9c4a94f9afd47f1aac64a59e35338486`, passes [198/198 checks](review/author-extendable-validation-2026-09-30.json), SHA-256 `504bf0b8e8500253ccf66b6d6d3914e06ae6685953e1067c8ffced29a490d6d1`, across source identity, raw seals, guarded execution, event ledger and report integration. A separate [independent read-only replay](review/independent_extendable_readonly.py), SHA-256 `75f10497715682309cf81ec5536aa0e8d3178f0226ecb0c649d509f5a58c6a0c`, passes [72/72 checks](review/independent-extendable-2026-09-30.json), SHA-256 `b26bbd9a599a66d2f0db38a5cd6e0ce1000be06761e5dfe0e95c3661576e8b5f`, without importing the author validator. Raw native files remain in ignored local `runs/`.

This evidence is specific to installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`, one seed and two observed stochastic failures. It does not supply the catalog's deterministic unavailable interval. No-interruption, other interruption patterns, crossing a result window, unfinished-at-horizon state, GUI visual content and cross-engine equivalence remain unverified. Issue #18 stays open.
