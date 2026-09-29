# D04 operation-hour PM: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one generic aircraft, a two-hour mission followed after a long no-flight gap by a one-hour mission, and one fixed one-hour PM after the `OPHOURS=3` threshold. The run establishes the observed trigger at the second return, not general PM timing under mission conflict, resource shortage, partial exposure, or further cycles.

## Source and execution

The accepted [D03 parent](../D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32`. Frozen [D04 input](native-input.json) SHA-256 is `d0b0ee5b74f3afe5f05b418771774adcf8ef987b0f553f1bfd535874955c790a`; the [parent diff](parent-diff.json) records a descriptive label, a new one-hour `SHORT-MISSION`, replacement of D03's 20/32-hour waves by one 40-hour wave, and the PM/task ID changes. The sole PM interval changes from `CALHOURS=24` to `OPHOURS=3`; the one-hour `INSPECT` subtask and 60-hour simulation/report window remain. The [contract](contract.json) SHA-256 is `74377c051ae5b1e01ba92fc930b30eb72fdafdfc5db6b681032bf38d79e68439`. The installed manual states that mission-hour counters advance on mission return (page 202), and documents `OPHOURS`/`PMINT` (pages 370–375); the actual trigger is established by this native run.

Native run `d04-flight-v100-ssh-20260930-01` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` mutex and active GUI PID 13340 guard. Import, export, calculation, JSON report and roundtrip checker exited zero. All 18 populated source tables roundtripped identically. Conversion had zero errors and two documented warnings: `#108` for event logging and `#126` for the intentionally item-free aircraft. Sealed invocation SHA-256 is `99a2bdae2639ec8575dfe28cc912b67e2b47d72bb0ab88bbca111e38e445735b`; closure SHA-256 is `3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45`. Raw native files remain under ignored local `runs/d04-flight-v100-ssh-20260930-01/`.

## Observed behavior and report

The aircraft completes `BASIC-MISSION` at 8–10 hours and `SHORT-MISSION` at 40–41 hours. It has no flight during 10–40; second-mission notification and preparation begin at 39. The event log has no PM before the second return. At 41, `OP3` starts its sole one-hour subtask at BASE-01; it completes at 42 and returns the aircraft ready. The earlier two-hour mission alone does not reach the three-hour threshold, and 30 intervening calendar hours do not cause a PM in this fixed case. Both missions succeed without abort or cancellation.

Raw event-log SHA-256 is `072310b8b29b69167d1a77df359144ad0b911748e512936271ef44f5009e084c`; raw JSON-report SHA-256 is `48261211d3346de355306cb1ab258a67765bfc9b037843847c673375239fda68`. The report has 120 contiguous half-hour system intervals through hour 60. `NPMS` marks one PM start at 41, `NPMT` one completion at 42; integrated `NSYPM` is one aircraft-hour and `NSYMO` is three flight aircraft-hours. No failures or repairs are reported; the terminal interval has one ready aircraft and no active PM.

## Review and limits

The [author raw replay](review/author-native-validation-2026-09-30.json) passed 65 checks; its report SHA-256 is `9e5f42a4baa5aed51fc0177e06b8cbaa631b8a4b1eaca3c98c5020fecdd6cf88`, and its [validator](validate_native_cli.py) SHA-256 is `5e612fb16816e131353b22dfb43b009715bdfbf37c3ab4016030b0028a6a54f5`. The validator was added after execution and performs read-only raw replay. A separate reviewer performed static prelaunch review and independent raw replay. Its [22-check review](review/independent-native-review-2026-09-30.json) passed with no differences; review SHA-256 is `f12f23f95101944b9b139eeab1d15c9ae2ede675d4bd711813d798316a5e2334`.

This case does not test calendar PM in parallel, more than one cycle of operation-hour PM, cumulative exposure under faults or partial missions, mission conflict, task queueing, resources, nonzero `ATIM/DTIM`, or item replacements. The GUI identity and active session were guarded, but GUI visual content was not sampled.
