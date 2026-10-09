# Independent v1.0.8 replay review — cycle chronology

**Decision: GO_SOURCE_REPAIR_ONLY; NO_GO_BEHAVIOR_ACCEPTANCE.** The `near(task_end, c_time)` condition in `validate_native_cli.py` line 192 is an out-of-contract restriction. It equates system replacement completion with completion of direct repair of the removed item. The frozen contract checks system SURP duration separately from damaged-item identity, one-hour direct repair, arrival, and stock return; it does not assert that these two tasks finish together. The accepted H02.var04 sign-off reports both replacement and one-hour removed-LRU repair without asserting simultaneous completion.

## Exact sources read

- v1.0.8 `contract.json`: 14,598 bytes, SHA-256 `3e47e87ba529ea1baa281d0d0dd83288720f0367fec7012a85a72409678c4da5`.
- v1.0.8 `validate_native_cli.py`: 18,156 bytes, SHA-256 `a16ee1a08d111f93b5426a06fdaf1ea5b3a85bfcff233921d7d4d6a0187d06b2`.
- v1.0.8 `test_surp_event_parser.py`: 1,189 bytes, SHA-256 `65cbc4337a0e5cc37962ad7d3130e09b8c36885dcad44e8bf43bd2a2728730a8`.
- v1.0.7 source `contract.json`: 14,214 bytes, SHA-256 `12cf9fd1382a7c693bf0af910c71a83bf9c31c3ee47f4cead12846b2dd426233`; its original failure seal is 6,315 bytes, SHA-256 `90ab30ca55d18d1432a9b4f5ae0aab8d15375361c6855c4231ff2224bed9e7a0`.
- Sealed v1.0.7 `model.log`: 18,330 bytes, SHA-256 `320ae836a31be9ac5273d913419c000934c82aea32db6431708d79071f1e82c5`. Its native closure records `behavior checker exit 1`; import, export, roundtrip, calculation, and JSON report stages exited zero.
- Accepted H02.var04 fallback `model.log`: 18,309 bytes, SHA-256 `bae8b9dae6be39c09dd3f546975c30f0b3bfe2b220ea6c948caa53553bc4a62a`; sign-off: 3,102 bytes, SHA-256 `53b9b4152f5f48d5d0003f0d4ad0257b5e5e933892dc85db2c810f8b6ee3681d`.

## Observed distinction

The three v1.0.7 system SURP tasks start/finish at 9.28145/10.7814, 21.2434/22.7434, and 32.6812/34.1812 hours. Each duration is 1.5 hours to the log's displayed precision. Direct repair of the removed item starts at 10.0314, 21.9934, and 33.4312, then finishes and returns that same item to stock at 11.0314, 22.9934, and 34.4312. Thus direct repair is one hour, and stock return occurs 0.25 hour after the corresponding system task finishes in each cycle. The tasks overlap; they are not the same task. In the accepted H02 fallback first cycle, system SURP finishes at 10.2814 while direct repair finishes and stock returns at 10.7814, a 0.5-hour difference. The proposed equality would reject the accepted parent's own topology.

The remaining line-192 checks have separate meanings: one-hour direct repair; repair completion, item arrival, and stock return at the same displayed time; system-task start aligned with spare issue. Removing only `near(task_end, c_time)` leaves those identity and chronology checks, the independently checked 1.5-hour system-task duration, and all later report-bin checks in place. Any replacement check must be justified prospectively from the contract, rather than fitted to these three times.

## Top-level parser and limit

The v1.0.8 regex uses a full-line match anchored at `Time:` for `system SURP task <id> on <TEACH-AIR-01,0> started/completed`. It excludes nested remove/fit subtask lines that the v1.0.7 substring search could count as duplicate top-level events. The two static regression cases cover nested `started` lines and duplicate true top-level `started` events. The full-line expression also excludes nested `completed` lines by construction; no separate completed-line regression case is present.

This review authorizes a distinct, source-only correction of the out-of-contract equality and subsequent independent replay of the same sealed v1.0.7 evidence. It does not accept the v1.0.7 run or the v1.0.8 replay: the latter stopped at line 192, so its downstream stock/report assertions have not been shown to pass. No accepted parent run, SIMLOX, SSH, preflight, project validator, or regression test was executed for this review. Raw originals and candidate source files were read only.
