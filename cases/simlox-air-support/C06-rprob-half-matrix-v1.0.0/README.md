# C06.var04: observed intermediate resource demand at RPROB 0.5

This bounded candidate derives from accepted [C06 RPROB=1 input](../C06-rprob-endpoints-v1.0.0/rprob-1-input.json), SHA-256 `0e548e167a48aed7e76dfeec5b0fbdfbb817f41bc3c88e0b1e246396ab218fa4`. Twelve complete frozen inputs change `SubTaskResource.RPROB` from one to 0.5, set explicit `Control.RSEED` strings 1–12, and update descriptive labels; seed 1 retains the parent's seed. Primary `P-CREW` and alternative `P-ALT` allocations remain zero. Each input has one native replication, the same two-aircraft formation and a 20-minute INSPECT preparation per aircraft. The [pre-run contract](contract.json) and [exact diff](exact-diff.json) show the complete controlled change.

All twelve guarded session-0 SSH runs completed import, export, calculation, reporting and exact roundtrip of 20 row-containing source tables, with zero conversion errors and only warnings #108/#126. Each aircraft's own availability test and work/wait events classify actual demand. `N` means its preparation performs 7.5–7.83333 without a typed P-CREW/P-ALT allocation; `D` means both typed availability checks fail and it waits. Native logs may say `books resources` for an `N` subtask as a generic event; the typed allocation events and resource ledger remain zero.

| Seed | Aircraft 0 | Aircraft 1 | Mission |
| --- | --- | --- | --- |
| 01 | N | D | cancels at 9 |
| 02 | D | N | cancels at 9 |
| 03 | N | D | cancels at 9 |
| 04 | D | N | cancels at 9 |
| 05 | N | N | succeeds 8–9 |
| 06 | D | D | cancels at 8.66667 |
| 07 | N | N | succeeds 8–9 |
| 08 | N | D | cancels at 9 |
| 09 | D | N | cancels at 9 |
| 10 | N | N | succeeds 8–9 |
| 11 | D | D | cancels at 8.66667 |
| 12 | N | N | succeeds 8–9 |

For mixed cases the resource-free aircraft completes preparation while the other keeps waiting; the one-waiter `NRW` report bins at 7.5–8, 8–8.5 and 8.5–9 are each one. Both-demand cases have waiting bins two, two and about two-thirds. Neither-demand cases have no resource wait and two aircraft in the hour-8 and hour-8.5 mission bins. All twelve terminal reports return two ready aircraft and have zero typed resource stock/use and zero inventory demand or movement. The [author replay](validate_native.py) checks each frozen source and raw seal, event classification, mission outcome, complete 72-bin resource/system/stock reports and terminal state. Raw native artifacts stay under ignored `runs/`.

This matrix observes all four patterns for these twelve seeds. The 4/3/3/2 counts are not an estimate of a 0.5 law or evidence of independent aircraft draws; no sampling test or confidence interval is claimed. Other seeds, replications, nonzero resource capacity, probability values, GUI-only behavior and cross-engine equivalence remain unverified.

To reproduce, run `build.py` and `describe_diff.py` to recheck frozen bytes, then use session-0 SSH to invoke `run_native_ssh.ps1 -Variant seed-NN -RunId <new-unique-id>` separately for each seed. The runner requires the pinned executable and working directory, the protected GUI PID 13340, and the host-wide Issue #18 mutex; it rejects reused run IDs. Check each new closure and explicitly adapt replay run IDs before accepting new evidence.
