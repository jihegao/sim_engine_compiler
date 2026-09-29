# D05 fault, PM and one-worker competition: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for the fixed one-critical-direct-repair versus two noncritical `CAL24` PM jobs sharing one worker. This is a restricted D05 teaching slice. The catalog's full D05 priority matrix and four boundary variants remain unaccepted.

## Frozen source and native execution

The direct accepted parent is [D03 calendar PM](../D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md), input SHA-256 `5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32`. Accepted D01, D04, and C03 independently establish the repair, operation-hour PM, and shared-worker prerequisites; D03 is the direct parent because its calendar boundary is fixed. [D05 input](native-input.json) SHA-256 is `4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad`. The [exact 15-table parent diff](parent-diff.json) SHA-256 is `8228d899140f46cd20b5ff68298d0bda0e3d2742f39a3571c6180ef2b6686237`; 16 other native tables remain identical.

The [contract](contract.json) freezes two aircraft, one allocated `P-MAINT` worker, a five-hour direct system repair with mandatory `<REPAIR>` subtask, and one-hour PM subtask with the same worker demand. `System.FRT=1000000` per million operation hours; `BASIC-MISSION` has zero failure multiplier and the three-hour second `RISK-MISSION` has multiplier one. The realized 22.6835-hour failure is observed from this seed and configuration, not a general guaranteed failure clock. `MaterielPM.DTIM=0.5` makes the observed PMs noncritical, while `Unit.MAXPM=2` leaves worker capacity as the active restriction. Horizon and both result windows are 36 hours.

Accepted native run ID: `d05-pilot-v100-ssh-20260930-03`. Its [session-0 SSH runner](run_native_ssh.ps1) guarded the host-wide `Global\SimloxIssue18NativeQueue` mutex and active GUI PID 13340. Import, export, calculation, JSON report, and roundtrip check all exited zero with GUI identity preserved. All **22 source row-containing tables** roundtripped exactly: 19 have at least one non-null field, while three contain all-null placeholder rows. The native export adds nine more all-null placeholder tables. Conversion had **zero errors**; warning #108 reflects enabled event logging, and #126 reflects the intentionally item-free aircraft. Native raw outputs are retained in the ignored local `runs/` directory and excluded from Git.

| Sealed raw record | SHA-256 |
| --- | --- |
| `invocation.json` | `32ca39008d2465e5c8de97bc69511131be7782e7a7b078706075ea42245285b0` |
| `closure.json` | `4ade4062f3ef3a25d8adc96b9f57f5ca34eea850de2fd2a304a4e0163fb55736` |
| `model.log` | `daeacfda91304217c1e3ac75e6842bd17de5ae2bac067fbf21aff82f96396fd5` |
| `report-raw.json` | `46975e779235a773b6e3473423dbb83a635cee9afd43baa77bb748f873cc406c` |

## Hand timeline versus observed timeline

| Boundary | Hand expectation | Native observation |
| --- | --- | --- |
| First and risk missions | Normal first mission; expose one risk failure in second | First mission succeeds 8–10; second starts 20, aircraft 1 fails critically and aborts 22.6835, returns 23 |
| Repair versus PM | Critical direct repair holds worker; noncritical PM waits | Repair on aircraft 1 books `P-MAINT` 23–28. Both PM task **objects** start at 24. Aircraft 0's PM subtask fails the worker test at 24, waits, and performs 28–29 |
| Second PM | PM on failed aircraft waits for its own repair and then worker | Aircraft 1's PM reactivates at 28, fails the worker test, performs 29–30 |
| Third mission and terminal state | Mission after maintenance can proceed; all resources released | Third mission succeeds 32–34; hour-36 state has two ready aircraft and one free worker |

The six native worker transactions are booking 23, release and rebooking 28, release and rebooking 29, and release 30. They never exceed one worker in use and end at zero held. The first PM's resource wait is 24–28 (four hours); the second PM's worker wait is 28–29 (one hour). Its preceding 24–28 delay is caused by its own outstanding critical repair, so the five worker-hours of aggregated wait must not be inflated to nine. In the 72 half-hour `SystemResults` and `ResourceResults` bins, `NFAIL=1`, `NREPT=1`, `NPMS=2`, `NPMT=2`; repair occupancy integrates to five aircraft-hours, PM occupancy to two aircraft-hours, worker use to seven hours, and worker wait to five hours. Mission success is two of three. The 24-hour PM task-object start markers are not evidence of physical concurrent PM work.

## Review, failed probes, and limits

The [author raw replay](review/author-native-validation-2026-09-30.json) passed **81/81** checks, SHA-256 `93910313b9db592325c12abf725b61753470b77e168b2ebeb1b1eab62f531a6a`; its [validator](validate_native_cli.py) SHA-256 is `be3aa24223aede17c4e88c5f18e9cd431229e6f08a9bdecc7b9957ae027e80a7`. A separate reviewer wrote a [standard-library-only, read-only replay](review/independent_readonly.py), SHA-256 `3ab7968681317e748e62eea231023e9996dfd60c0d7fa45cf5bd0770688cd28f`, without importing author code; the [51/51 independent result](review/independent-readonly-2026-09-30.json), SHA-256 `41f1a1eb90d01b299b014c2837783cff40cb3379b8d7a81c6545d44b4dd0039f`, agrees on the source and native ledger.

Two earlier pilot directories are retained locally and excluded from acceptance. `-01` failed native conversion with #162 because a custom `REPAIR` was used instead of reserved `<REPAIR>`. `-02` ran but produced two failures with a higher fault rate and initially failed a roundtrip checker count assertion; it does not support the single-failure teaching contract. These failures motivated the corrected, newly sealed `-03` run.

This release demonstrates the observed critical repair occupying the only worker ahead of noncritical PM, followed by serialized PM execution and a later successful mission. It does **not** establish general same-time event priority, noncritical fault versus PM order, critical PM override, PM deferment expiry, alternative worker capacities, mission cancellation caused by the maintenance wait, other seeds, later PM cycles, GUI visual behavior, or cross-engine equivalence. The GUI process was guarded but its visual content was not sampled. Issue #18's full completion standard remains open.
