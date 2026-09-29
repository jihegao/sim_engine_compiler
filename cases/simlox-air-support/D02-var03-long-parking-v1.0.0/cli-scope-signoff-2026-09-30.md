# D02.var03 130-hour long parking: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed traditional installed-LRU `OPHOURS` run with 130 hours without flight between the second and third missions. This records the observed native behavior, not a general clock rule.

## Parent, source and frozen input

The accepted [D02.var01 parent](../D02-var01-traditional-op-hours-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2`. The [D02.var03 child](native-input.json) input SHA-256 is `c1bd1294a126b199e16d55fd66ae084d382683416581b67772d7e82e532f6e24`. The [exact parent diff](parent-diff.json), SHA-256 `be20c36f30d3971d4c85b157f9b6c9d70fa3fb9b10c3fc16539a0a806907831a`, changes only the description; third scheduled `OperationProfile.STIM` 52→152; `Control.SIMPE/RCEND` 60→160; and both `ResultCollection.RCEND` values 60→160. The other 27 parent tables are unchanged. In particular, `System` and `Item` retain traditional `OPID=OPHOURS` and FRT=300000 per million hours; LRU, spare, repair, seed and first two missions are unchanged. The [contract](contract.json) was frozen before the native run.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; the installed dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The accepted parent and manual define the traditional-clock source boundary. Proprietary sources are not uploaded.

## Native evidence and observed comparison

Run `d02-var03-long-park-v100-ssh-20260930-01` used session-0 SSH, host-wide `Global\SimloxIssue18NativeQueue` and the GUI PID 13340 identity guard. Import, export, calculation, report and roundtrip checker exited zero. All 18 row-containing source tables roundtripped exactly. Conversion had zero errors and one warning, #108 for event logging. The source-bound run retained raw files locally under ignored `runs/`.

The first two missions and installed-LRU path match D02.var01: first mission abort and traditional failure at 9.8829, local spare issued at 10, system replacement complete at 10.5, failed item repaired and restocked at 11.25, and second mission success at 22. There is no flight or failure during hours 22–152. The aircraft remains ready in the parked report bins through hour 151, enters preparation during 151–152, and the third mission starts at 152 and succeeds at 154. The parent instead starts its third mission at 52 and succeeds at 54. Its later prospective failure time shifts by 100 hours in the child log; that observation is not used as a general random-stream claim.

The child report has 320 aligned half-hour `SystemResults` bins through hour 160, totaling `NFAIL=1` and `NREPT=1`, with 12 half-hour bins reporting mission operation across its three scheduled missions. Stock reports one demand and zero backorders. One aircraft is ready at the hour-160 stop. The report's mission success fraction is 2/3, consistent with the event log's aborted first and successful second and third missions.

| Child raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `caed717fb4306f5f6abd30dbd9e688da595145c309e4de0f57185d55ae0ea48c` |
| `closure.json` | `5b69dc1f1d7753f829b6793451b82f05aeeaf6040f5a3493e69ae7bb2270767b` |
| `model.log` | `4b6bffbe414a091f39e8a97bdf0668bd5e6137c683b7b487d0f3074a44fb5a1c` |
| `report-raw.json` | `65b4ad6d16a9c362c8d4d494787cdab3d4cd2d0882c827bac60a36b3c26417c7` |

The [author validator](validate_long_parking.py), SHA-256 `90f9fa44aeb28968a5a46901a060a1fb82f10e531753414bbc1c4b977f75850f`, passes [66/66 checks](review/author-long-parking-validation-2026-09-30.json), SHA-256 `b758145e28ab3556df349650806a510224c1e1bcf0d9a0f1ada3327134d21125`. A separate reviewer wrote a [read-only replay](review/independent_long_parking_readonly.py), SHA-256 `7e850bda8dab4a310fe9e3ad1f1d5c3eca9c813f6bf068dc879ac1f92d5f0e35`, without importing the author validator. Its [92/92 result](review/independent-long-parking-2026-09-30.json), SHA-256 `1a2d905b6504f25ae69868a3e5b17ca2c5cfad01666cfdc56d158bf3461040d8`, independently checks frozen source and diff, raw closure, guard, roundtrip, parent events, parking interval and report ledger.

This scope uses installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0` and one seed. No internal `OPHOURS` counter is directly reported. Other seeds, PM during parking, dynamic changes, GUI visual content and cross-engine equivalence remain unverified. Issue #18 stays open.
