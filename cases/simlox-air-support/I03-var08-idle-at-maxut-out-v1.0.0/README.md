# I03.var08: idle crew at the MAXUT limit

This prospective case adds one P-CREW ResourceTransfer OUT request at hour 24.75 to the accepted C08 exact-limit source. Two crew have just finished preparation and the first shift has printed zero remaining MAXUT. The hypothesis is an immediate, quantity-one OUT task while that crew is idle. The accepted C08 run is read only and is never repeated for this case.

The source changes are exactly one inserted seven-column ResourceTransfer table and the ProblemDescription cell. `native-input.json` and `exact-diff.json` are deterministic outputs of `build.py`. The prospective event and report gates expect 175 log lines, 113 timed records, and all 5,210 report cells. These are predictions, not a native result.

`contract.json` is the frozen prospective design. `execution-contract.json` binds its hash to this package, run ID, and six-stage protocol; neither file authorizes native execution. Root must freeze the source manifest, obtain independent pure review, run an actual zero-native SSH PowerShell 5 preflight and obtain a separate exact GO_PRELAUNCH before the sole native run.

The fixed test concerns this one source and time. Physical local quantity, nominal quantity, printed shift-free quantity, NRA presentation and remaining MAXUT budget are checked separately. The case makes no resource-person identity or general MAXUT rule claim.
