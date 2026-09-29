# D05.var01 zero-worker horizon boundary: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for this fixed-seed, zero-worker, hour-36 pending-work boundary. The native model converts and runs successfully. No corrective repair or PM completes; these are expected observed outcomes, not a failed acceptance. The accepted [one-worker D05 case](../D05-maintenance-competition-v1.0.0/cli-scope-signoff-2026-09-30.md) and [two-worker control](../D05-var01-two-workers-v1.0.0/cli-scope-signoff-2026-09-30.md) provide the other D05.var01 capacity points.

## Source and native evidence

The accepted one-worker parent input SHA-256 is `4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad`; the [zero-worker input](native-input.json) SHA-256 is `e8ef846a1f5c87e2fce982baaa3c5057b2f9554f3a620b09c49d6ecb8bd4e158`. The [exact parent diff](parent-diff.json), SHA-256 `fd90d74f53814de4a36ad8c357d1fdd338c9f6f981a77d2345925390cfc69a4e`, changes only three tables: `ResourceAllocation.RQTY=1→0` is the sole behavioral field change, with two descriptive labels. Seed, fault rate, aircraft/mission schedule, repair and PM work specifications, per-subtask worker requests, `MAXPM=2`, and hour-36 horizon remain fixed. The [contract](contract.json) records the original probe hypothesis; outcome is determined from native evidence below.

Native run ID `d05-var01-zero-v100-ssh-20260930-01` used session-0 SSH, host-wide `Global\SimloxIssue18NativeQueue`, and active GUI PID 13340 identity guard. Import, export, calculation, JSON report and roundtrip checker all exited zero. All 22 source row-containing tables roundtripped exactly; three include all-null source placeholder rows, and native export adds nine all-null placeholder tables. Conversion had zero errors and the documented #108 logging and #126 item-free warnings. Raw artifacts remain in ignored local `runs/`.

| Zero-worker raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `68745b7533dde64d113dbb9a82963ae9758d72293f7182512769a5508ccea785` |
| `closure.json` | `a055fe2b7063686abf20fe01623aab7eb73858d71bee256ce886ca775d865030` |
| `model.log` | `d23dd28335720b121b51bff4d3539de54d7a56c84bb001dda0ab0b2c933f5da2` |
| `report-raw.json` | `a164b60ebc2de4cf7910b92ba2786028dc0bb54607aa1672eb286aef753b6d93` |

## Observed pending-work timeline

The first mission succeeds 8–10. Aircraft 1 starts the second mission at 20, fails critically at 22.6835 and aborts; it returns at 23. The direct repair task starts at 23, requests one `P-MAINT` worker and fails the availability test. Both aircraft's `CAL24` PM task objects start at 24. The healthy aircraft's PM also requests one worker and fails the test. The faulted aircraft's PM is held behind its own unfinished critical repair and does not yet request a worker. A task-object start at 24 is not performed maintenance.

At 31 the healthy aircraft's noncritical PM resource wait is paused when that aircraft is allocated to the third mission. The mission starts at 32 and succeeds at 34; after its return the PM continues, requests a worker again and still cannot start. The critical repair remains pending. At the hour-36 stop there is no repair or PM subtask performance or completion, no worker booking or use, one ready aircraft and one aircraft still waiting for repair resources. The terminal resource report has two waiting requests: the direct repair and the healthy PM. This is **only the observed state through hour 36**; no post-horizon repair or priority is inferred.

The 72 aligned half-hour report bins give `NFAIL=1`, `NREPT=0`, `NPMS=2`, `NPMT=0`, and zero repair, PM and worker-use hours. `ResourceResults.NRW` integrates to approximately **22 summed worker-request hours**: repair 23–36 (13), healthy PM 24–31 (7), and healthy PM after return 34–36 (2). It is a sum across pending requests; the failed aircraft's PM does not contribute a separate worker request because its own critical repair is unfinished. `SystemResults.NSYWR` integrates to **13 aircraft-hours** and is not interchangeable with the 22 request-hours. Mission success remains two of three despite unfinished PM on the healthy aircraft.

## Review and limits

The [author raw replay](review/author-zero-validation-2026-09-30.json) passed **67/67** checks, SHA-256 `89ca3bcbd9dc3142f5e45a5bd13fa893d636bf29ae3fb1e51e35788c40b66c07`; its [validator](validate_zero.py) SHA-256 is `b3b4fd63d9212b8180f67bc404b163c5ea2294eb5387309478453468a4b3a557`. A separate reviewer wrote a [standalone read-only replay](review/independent_zero_readonly.py), SHA-256 `ae64cfb176b0d8b11b9844a9e41371f017b96935ce014001be23c434e5e15343`, without importing author code. Its [64/64 result](review/independent-zero-2026-09-30.json), SHA-256 `ef74e30215de78daeb45478fb989f8eece108f85154bbabccf42b327322b5ce9`, agrees with the source, event log, report and terminal state.

This release covers a single zero-worker native run at a fixed seed and horizon, compared with an accepted one-worker input. It does not establish how pending tasks end after hour 36, behavior with intermittent staffing, other failure draws, PM criticality transitions, same-time priority, GUI visual content, or cross-engine equivalence. The GUI process was guarded but its visual content was not sampled. Issue #18 stays open.
