# D13.var01 local PM activation off/on: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed local `PMActivationProfile` that disables `CAL24` PM during hours 0–30 and enables it during 30–60. This is a bounded period-switch result, not a general PM scheduling or counter algorithm claim.

## Source and native run

The accepted [D03 parent](../D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32`. The [D13.var01 input](native-input.json) SHA-256 is `f4fce5c8f362be817264544f22f271c1ee47b6e635e871619525fa1c8545ca70`; the [exact parent diff](parent-diff.json), SHA-256 `e7f78ae5bedbc46051d81e765f43bca64056ce32d5ecc169b4b69e52f1c1c68c`, adds `PMActivation` and `PMActivationProfile` and changes only `ProblemDescription` among the 31 parent tables. The local row links `TEACH-UNIT/CAL24` to profile `PM-SWITCH`, which has explicit nonoverlapping `<LIMIT>` periods `ENPM=N` 0–30 and `ENPM=Y` 30–60. `Control.ENPM=Y`, missions, PM interval, seed and result horizon are unchanged. The [contract](contract.json) freezes the hypothesis.

The installed SIMLOX 2017 manual, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, pages 379–385, documents the local/time-dependent activation distinction and continued counter updates during disablement; its field dictionary supplies the column definitions. Native behavior is established by the run, not by the manual alone. Neither proprietary source is uploaded.

Native run ID `d13-var01-activation-v100-ssh-20260930-01` used session-0 SSH, host-wide `Global\SimloxIssue18NativeQueue` and the active GUI PID 13340 guard. Import, export, calculation, report and roundtrip checker all exited zero. All 20 source row-containing tables roundtripped exactly. Conversion had **zero errors and two expected warnings**, #108 for event logging and #126 for the item-free aircraft. Raw artifacts remain in ignored local `runs/`.

| Accepted raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `306349746948d5d7e79c2fe2efb15cf3544932d58f2fc184592ecacae3ba842f` |
| `closure.json` | `0bebe4cfd9a039bfc6bb1e2f9391f2a985ca2d199da97e76f17a105396cd0e91` |
| `model.log` | `739170073ebe6e5e7c05e935e3226f8f2469ac1b83f74c4964db8363ba364f3f` |
| `report-raw.json` | `d04d1e3891585296c277a89ff17dc58a14159e89ddeb61fc7e377c46dba20a1f` |

## Observed comparison and review

The D03 control performs one-hour PM at 24–25 and 49–50. In the profile run there is no PM object or work at hour 24, despite the unchanged `CALHOURS=24` input. At the 30-hour enable boundary, the first PM task and its one-hour subtask start immediately and complete at 31. The second task performs 55–56. The three unchanged missions still start at 8, 20 and 32 and succeed at 10, 22 and 34; at hour 31 the third mission briefly waits for the aircraft finishing PM and is allocated in that same hour. The 120 aligned half-hour report bins have `NPMS=2`, `NPMT=2`, zero failures/repairs, two aircraft-hours of PM, six aircraft-hours of mission operation and one ready aircraft at the hour-60 stop.

The [author raw replay](review/author-activation-validation-2026-09-30.json) passed **63/63** checks, SHA-256 `fad1c423c7407a2a4becb73c08e017b6bb1e0b5ae417bd889b6a6dc9aa5755a1`. Its [validator](validate_activation.py) SHA-256 is `b2054dde495b4d92009adecb822fc9253b07331577823d2439c9a53f0deda8fa`. A separate reviewer wrote a [standard-library-only read-only replay](review/independent_activation_readonly.py), SHA-256 `aff2352aca0b1850588ff9ab64ed91cca778f3862951a6daa25450aab39547ae`, without importing author code. Its [51/51 result](review/independent-activation-2026-09-30.json), SHA-256 `b9acc9b69705e8183742f05932d4859d3e4523a670be9c359b63961a9474de16`, agrees with the exact delta, sealed raw run, PM and mission events, and report ledgers.

The log does not expose the per-PM internal counter. Continued accumulation while disabled is documented by the manual and consistent with PM beginning at re-enable, but is an inference from timing, not a measured counter trace. This result does not establish other disable/enable boundaries, global `Control.ENPM=N`, transfer between units, `CRIT=N`, repeated or nested activation profiles, GUI visual content or cross-engine equivalence. The GUI identity and active session were guarded, but its visual content was not sampled. Issue #18 stays open.
