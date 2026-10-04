# F04.var01 eight aircraft over 43 days, no-failure regression

This bounded teaching case extends the accepted F03.var01 staffed two-base fleet. BASE-01 has five aircraft and BASE-02 three. Both root profiles request 21 waves spaced 48 hours apart across a 1032-hour horizon. System and item failure rates are zero, and all mission type random failure factors remain zero. The [contract](contract.json) and [exact diff](exact-diff.json) freeze 14 changed parent cells. Accepted J04–J08 reporting prerequisites are fingerprinted in the contract.

Two fresh guarded native runs have identical event logs and reports. Each has 21 BASE-02, 21 RISK and 21 BASIC mission starts and successes, yielding 105 sorties and 210 aircraft operating hours. No fault, item demand or backorder occurs. CAL24 PM starts 324 times and completes 323 times. The final PM starts on BASE-02 aircraft 6 at h1031 and is still active at h1032: terminal aircraft are seven ready and one in PM, with one maintainer booked and no queue or backorder. All 2,064 half-hour System, Stock and Resource bins reconcile with event-derived state and worker use.

The earlier local v1.0.0 pair is excluded: IQTY21/IPER48 produced compressed 2.2857-hour demand spacing. Its two diagnostic closures remain sealed locally and are identified in [author validation](author-validation-2026-10-04.json). The corrected v1.0.1 source uses IPER1008 on both root profiles; its native events confirm 48-hour spacing.

## Reproduce and limits

Run python build.py and python describe_diff.py to verify frozen source bytes. Invoke run_native_ssh.ps1 with Arm repeat_a or repeat_b and a fresh RunId serially under session-0 SSH; it enforces source pins, sshd ancestry, the host mutex, active GUI PID13340, reviewed converter warnings, native import/export/calc/report, exact source-table roundtrip and local raw closure. Run python validate_native.py for the accepted two-run replay. A separate [independent replay](review/independent_replay.py) and [evidence index](evidence-index.json) verify and seal the result.

This is one seed and one replication in each of two repeated deterministic runs. It does not measure stochastic variance, confidence precision, multi-replication stability, later resource-policy contrasts, broader failure/supply behavior, GUI visuals or cross-engine equivalence. F04 and Issue #18 remain open.
