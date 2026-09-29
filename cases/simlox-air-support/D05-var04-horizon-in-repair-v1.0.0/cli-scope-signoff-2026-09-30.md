# D05.var04 repair-in-progress horizon: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for a fixed-seed, positive-worker direct repair still performing at hour 26. This is the “in repair” boundary only; a separate waiting-for-repair boundary is not claimed here. The accepted [D05 one-worker parent](../D05-maintenance-competition-v1.0.0/cli-scope-signoff-2026-09-30.md) supplies the completed hour-36 counterpart.

## Source and native evidence

The parent input SHA-256 is `4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad`; the [frozen child input](native-input.json) SHA-256 is `c079a64d31f1b4ae2d7d537d1546bc5277bf20bcc55353aa7d1c4f487edd2b74`. The [exact parent diff](parent-diff.json), SHA-256 `a2d4881edc912f78ab1976450899586b7f1f7db4b0a6029e95f396c8148ac812`, changes only `ProblemDescription` (label), `Control` (36→26 stop/window), `OperationProfile` (removes the out-of-window third mission at 32), and `ResultCollection` (both 36→26 end fields). The other 27 tables, including worker capacity one, repair and PM specifications, seed and failure rate, remain unchanged. The [contract](contract.json) freezes the tested hypothesis.

Accepted run ID `d05-var04-horizon-v100-ssh-20260930-02` used session-0 SSH, host-wide `Global\SimloxIssue18NativeQueue`, and active GUI PID 13340 identity guards. Import, export, calculation, report and roundtrip checker completed with exit zero. All 22 source row-containing tables roundtripped exactly; three source tables have all-null placeholder rows and native export adds nine all-null default tables. Conversion had zero errors, with warning #108 (event logging) and #126 (item-free system). The raw artifacts remain in ignored local `runs/`.

| Accepted raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `e8a5bd7b8a6c858dd207fc7b9499982c9af5704e8fe216203e7db0fc4d2b58c2` |
| `closure.json` | `7aa9af3e00a041083dd940e631061c598cb2e74a99482be3eeae511c8cdc7588` |
| `model.log` | `ae51ab38197bff4c3b6621d1803e887542a4d97d95c933a20078abf17bef4d69` |
| `report-raw.json` | `e7b9d20c4fcfb2cd09026a59203016842fe9c393757670775322f6a45a1c19c5` |

## Observed timeline and ledgers

The first mission succeeds at 10. The second starts at 20, has one critical failure at 22.6835, and aborts. Its direct repair task and five-hour work start at 23, booking the one `P-MAINT` worker. Both CAL24 PM task objects start at 24; the healthy aircraft's PM fails a worker availability test, and the failed aircraft's PM has not reached physical work. At hour 26 there is no repair or PM completion or worker deallocation event. The terminal half-hour report bin has one ready aircraft, one aircraft in repair, one worker in use and one PM worker request waiting. A task-object start is not performed PM.

The 52 half-hour report bins sum to `NFAIL=1`, `NREPT=0`, `NPMS=2`, `NPMT=0`. They integrate three aircraft-hours of repair occupancy, zero PM occupancy, three worker-hours used, and approximately two summed worker-request waiting hours. One of two missions succeeds (`MSUF=0.5`). `ResourceResults.NRA=1` coexists with `NRUM=1` in the final bin; this scope does not interpret `NRA` as an unbooked worker at the stop. The in-progress conclusion comes from the work-start and absent-completion events, `NSYRP=1` and `NRUM=1` in the final bin.

## Review and limits

The [author validator](validate_horizon.py), SHA-256 `23014df49cfe370f0db8863ca7bb60e6ba1ee3f37e8baabce10d3d416958f9c8`, passed [74/74 raw-evidence checks](review/author-horizon-validation-2026-09-30.json), SHA-256 `0f269cac3e1fde1a8e3ba4153e35f1b02f8720e502b07e18785e4d837d501de6`. A separate reviewer wrote a [standard-library-only read-only replay](review/independent_horizon_readonly.py), SHA-256 `b7359241352307a9a465383917f7983a29dac5fb84d5133d609723fe5bcd3556`, without importing author code. Its [59/59 result](review/independent-horizon-2026-09-30.json), SHA-256 `8372364e45833fe260d2805565aee597b0deec5d8be5c909a397aabf0a6c064a`, confirms the exact delta, sealed native artifacts, observed events, 52-bin ledgers, and failed-probe exclusion.

An initial immutable candidate, `d05-var04-horizon-v100-ssh-20260930-01`, retained the third mission after the new stop. Native conversion failed with error #204 (“Some missions may not return before simulation period ends”), produced only a four-byte `.sxo`, and was excluded. Its input SHA-256 is `a727f5613ff157832ac3be41b15d0df300549c2be378a6b2b58acf3c14cd2e2d`; its `run.log` SHA-256 is `c12df9722ee3b2afb20b665ad5c8a5eed9086bfa1e6c432708f86680a8cd6676`. The failed run remains sealed locally.

This scope does not establish how repair or PM ends after hour 26, whether the final native shift-end event releases or rebooks a worker, the waiting-for-repair branch of D05.var04, other random draws, same-time priority, GUI visual content or cross-engine equivalence. The GUI process identity and active session were guarded, but visual content was not sampled. Issue #18 stays open.
