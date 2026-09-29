# D13.var02 simultaneous PM capacity: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for this paired `Unit.MAXPM=1` versus `2` comparison. Two generic aircraft at one unit reach a noncritical `CALHOURS=24` PM boundary. The comparison establishes one versus two **simultaneously performing one-hour PM subtasks** in this fixed configuration. It does not establish general priority for critical PM, faults, repair resource contention, mission conflict, PM activation periods, or later cycles.

## Frozen source and native runs

The accepted [D03 parent](../D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `5f2f74e6fe19df29d691ca44601a04a8c9a3663cbeca07f33c18a01b7c0f1a32`. The [MAXPM=1 input](../D13-var02-maxpm-one-v1.0.0/native-input.json) SHA-256 is `8881ab42a492ce066dd23a51830b039768c316282e241fd45ee73d0ed5ee9748`; its [parent diff](../D13-var02-maxpm-one-v1.0.0/parent-diff.json) adds a second deployed aircraft, sets `Unit.MAXPM=1`, changes `MaterielPM.DTIM=0→0.5`, and shortens simulation and both result windows to 36 hours. `ATIM=0`, `CALHOURS=24`, one-hour PM task and the three A02 mission waves remain. The installed manual says `MAXPM` limits simultaneous PM but has no effect when both `ATIM` and `DTIM` are zero (page 379). The nonzero deferment creates a noncritical window through this pair's observed PM completion; no critical boundary event is accepted.

The [MAXPM=2 input](native-input.json) SHA-256 is `d65ba7873f89e9b8e391b731a04aaa9622b346b6f8fa7d4547e177b42a285e41`. Its [parent diff](parent-diff.json) changes only `Unit.MAXPM=1→2` and the descriptive label; every other business field is identical. The [capacity-one contract](../D13-var02-maxpm-one-v1.0.0/contract.json) and [capacity-two contract](contract.json) bind their respective source fingerprints and predicted bounds. Both runs used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` mutex and active GUI PID 13340 guard. Import, export, calculation, JSON report and roundtrip checker all exited zero; each run roundtripped its 18 populated source tables exactly. Each conversion had zero errors and two documented warnings: `#108` for event logging and `#126` for the intentionally item-free aircraft. Proprietary raw native outputs remain in ignored local run directories.

| Capacity | Native run ID | Invocation SHA-256 | Closure SHA-256 | Raw log SHA-256 | Raw report SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `MAXPM=1` | `d13-maxpm-one-v100-ssh-20260930-01` | `706fb047ea141ff749b66c8a052cfb1464e0e15f2dda7e554a4c5fb4a6842497` | `306cdab4bc745b96d98e77a5f8700c72bae2c8adfb9638f5defd5f56f9186f57` | `00c4f7af857ecc3375d8d48d26afd07820d4e86b3d5d928a2c751a7fbc5fa2d5` | `7973cc682432f3855ce3d7bd0463fd6d81bb2547c776c25299c18cef82c16877` |
| `MAXPM=2` | `d13-maxpm-two-v100-ssh-20260930-01` | `cff726ba8437d2fa19d80c770d9c85b0e7f15591d0defd6a8f4211198f7a45f0` | `7d577663225a98f5f0406cc3e77d3c3cc74cd8fe6f340457363c85e74a976d9d` | `585f69838355a74d9670eba62b7c006c49fec79bd3976f5ce6da59dbe9ad44c4` | `a0785a2787387e648a5026ebfd343e8cb31e45e69e4d72948d0165b0dd9c85ea` |

## Observed comparison

In **both runs**, the event log marks PM task objects for distinct aircraft instances 0 and 1 as started at hour 24. This task-object marker alone does not show concurrent physical work. At `MAXPM=1`, aircraft 0's subtask performs 24–25; aircraft 1's subtask is reactivated at 25 and performs 25–26. At `MAXPM=2`, both subtasks perform 24–25. The 72 aligned half-hour `SystemResults` intervals show `NPMS=2` at 24 in both runs, `NPMT=1` at 25 and 26 versus `NPMT=2` at 25, and peak `NSYPM` of one versus two aircraft. Integrated PM occupancy is two aircraft-hours in each run. Both aircraft are ready at the end.

The three one-aircraft missions still run 8–10, 20–22 and 32–34 hours and complete successfully, with no cancellation or failure. PM work finishes before the third mission is allocated at 31. This pair has no PM resource demand, so the difference comes from `MAXPM` in this bounded configuration, rather than crew capacity. The 36-hour stop does not observe a later PM cycle or a critical transition.

## Review and limits

The [author pair replay](review/author-pair-validation-2026-09-30.json) passed 104 checks; report SHA-256 is `d40446eda30ed8f20eb889c0ab51908be003c04a7279fae33cedf7d9f43ac8fa`. Its [validator](validate_pair.py) SHA-256 is `9e4f25329ea05205bd425dce4dc5c58b2cc876979d962ee930df35aff6ccd0ae`; it was added after execution as read-only raw replay. A separate reviewer checked both sources before launch and independently replayed both raw runs. Its [35-check review](review/independent-pair-review-2026-09-30.json) passed with no differences; review SHA-256 is `fb9ac2528f91a48da0eebcdef54b12bb6578e3a8d47800b500f3a2e755d053fd`.

This release covers D13.var02's static capacity comparison only. D13's PM activation period variant, dynamic `MaxPMProfile`, PM criticality override, resource competition, mission conflict and beyond-horizon work require separate evidence. The GUI identity and active session were guarded, but visual content was not sampled.
