# J01.var03 triangular preparation distribution

This package tests catalog variant `J01.var03` against the accepted
`J01.var01@1.0.0` input. Seed 01 changes only `MissionPreparation.DURND`
from `PREP-DET` to `PREP-TRI` and its `TimeDistributions` row to
`PREP-TRI`, `PFAC=1`, `BASED=<TRIANG>`, `PARAM1=0.25` lower,
`PARAM2=0.5` mode and `PARAM3=0.75` upper hour. Mandatory `DURN=0.5`
hour remains. Seeds 02–12 differ from seed 01 only in `Control.RSEED`;
all inputs have `NREPS=1`. Run `build.py --check` to verify the frozen
inputs and `panel-diff.json`.

The installed database dictionary lists the native `<TRIANG>` enum. The
installed manual, pp. 543–545, spells the distribution `<TRIANGULAR>` and
gives the lower/mode/upper parameter order. The native converter accepted
and exported `<TRIANG>` with those three values. `contract.json` pins both
proprietary source hashes; neither source file is included here.

For each seed, call `run_native_ssh.ps1` inside an authenticated session-0
SSH connection with a PTY, fresh `-RunId`, matching `-Seed` and
`-InputSha256` from `panel-diff.json`, and `-AllowExistingGui`. The runner
checks the native executable and GUI PID 13340/start identity, acquires the
host-wide Issue #18 mutex, and seals raw artifacts even after a failed
native step. `validate.py RUN_DIRECTORY SEED` replays one run without
calling SIMLOX. `validate_panel.py` checks all twelve runs. Their ignored
`runs/` directories remain local and their raw SHA-256 seals are published
in `evidence-index.json`.

These twelve fixed-seed draws document native import/export and observed
preparation durations within the frozen bounds. Descriptive sample
statistics do not prove the population law, mode, independence or endpoint
attainment. GUI-only behavior, other J01 variants and cross-engine parity
remain unverified.
