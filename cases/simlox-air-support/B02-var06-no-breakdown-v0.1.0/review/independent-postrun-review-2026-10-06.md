# B02.var06 no-breakdown independent postrun review

**Decision: GO_BOUNDED.** My separately authored, read-only `independent_replay.py` passed **4,346/4,346** checks with no failures; `independent-verdict.json` contains the machine-readable result. I did not import or call the author validator or invoke SIMLOX or the protected GUI.

## Lineage and native run

The single child run is `b02-var06-no-breakdown-v010-ssh-20261006-01`, closure SHA-256 `4d6e84b6d32da692ff95219a149af547a9e196cf548adf3ad6968d2d8f72250f`. The closure source hashes match the actual pinned files and are identical before and after execution. All 12 child, 11 accepted B02 parent, and 11 accepted B01 prerequisite raw files match closure SHA-256 and byte-size seals. Contract SHA is `41b8b74938b0b21d7fb2353cc9d5d40d7eb935bcd249084d146483311a7ededa`; child input SHA is `7596ea50dc770bf9726a0d3300c0c2b0a881b772e57db0c3a079a3629714a939` and is byte-identical to the run copy.

The invocation records actual SSH session 0 with sshd ancestry, `Global\SimloxIssue18NativeQueue`, and protected GUI PID 13340/session 1/start 1790590196826. Import, export, roundtrip check, calc, and JSON report ran in order with exit code zero and GUI preservation recorded for each step. The converter reports Errors 0, Warnings 2 (#108 and #126 only), Notes 0, and produced a substantive SXO.

## Source, events, and report

- The only change from accepted B02 source is removal of the two `TaskBreakDown` instance rows for `PREP-FIXED`; the empty table and all other tables, columns, instances and rows are retained. `MissionPreparation.DURN` remains 0.75 hour. All 16 authored row-containing tables roundtrip exactly. Native export represents the authored empty `TaskBreakDown` as one all-null placeholder row; it contains no populated breakdown cell.
- The log assigns physical aircraft `<TEACH-AIR-01,0>` at h7. Its linked preparation and main task start then. Native creates one synthetic `subtask 0 seqno 0`, starts it h7, plans 0.75 hour, and completes it h7.75. The main task and preparation complete at h7.75. No authored SEQ1/SEQ2 lifecycle, resource wait, or cancellation appears. The same aircraft launches h8, performs the mission task h8.5–9.5, and succeeds/returns h10. Accepted B01 independently demonstrates the same synthetic `seqno 0` form with a 0.5-hour scalar; the child run establishes this case's 0.75-hour result.
- Every field in the 72×40 `SystemResults` grid was compared with the accepted B02 parent. Exactly two cells differ: in [7.5,8), `NSYMP` changes 0→0.5 and `NSYMR` changes 1→0.5. All other System cells, all 72×16 `StockTotalResults` cells, all 11 `ResultSummary` fields, and `ProblemDescription` match the parent. The child integrals are ready 33, preparation 0.75, reserved 0.25 and flight 2 aircraft-hours, with terminal ready 1.

## Limits

The inherited `Tasks.DESCR` still says “Serial 10+20-minute”, a stale human label. The retained `SubTaskType` definitions were not performed. This result supports only the one fixed-seed, one-aircraft, one-mission, linked-task case without authored breakdown or resource demand. It does not establish general scalar fallback across durations, seeds or task types, GUI visual behavior, repeated mission effects, cross-engine equivalence, or full Issue 18 coverage.
