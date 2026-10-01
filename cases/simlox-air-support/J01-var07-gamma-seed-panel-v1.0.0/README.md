# J01.var07 GAMMA preparation distribution

This package tests catalog variant `J01.var07` against the accepted
`J01.var01@1.0.0` input. Seed 01 changes only `MissionPreparation.DURND`
from `PREP-DET` to `PREP-GAM` and its `TimeDistributions` row to
`PREP-GAM`, `PFAC=1`, `BASED=<GAMMA>`, `PARAM1=2` (`n`) and
`PARAM2=0.5` (`Beta`). Mandatory `DURN=0.5` hour remains. Seeds 02–12
differ from seed 01 only in `Control.RSEED`; all have `NREPS=1`. Run
`build.py --check` to verify the inputs and panel diff.

The installed database dictionary permits `<GAMMA>` and the installed
manual pp. 542–545 names `n` and `Beta` as its parameters. Native
import/export retained the input row. Proprietary sources are pinned
by SHA-256 in `contract.json` and are not included here.

Run each seed through `run_native_ssh.ps1` in an authenticated session-0
SSH connection with a PTY, fresh `-RunId`, matching `-Seed` and
`-InputSha256` from `panel-diff.json`, and `-AllowExistingGui`. The
runner checks GUI PID 13340 and its start identity, native executable,
source hashes and the host-wide Issue #18 mutex. It seals partial raw
evidence after a failed step. `validate.py RUN_DIRECTORY SEED` replays
one run without SIMLOX; `validate_panel.py` checks all twelve accepted
runs. Ignored local `runs/` folders and raw SHA-256 seals are indexed
in `evidence-index.json`.

The twelve accepted fixed seeds have distinct, positive preparation
durations within the one-hour notice, followed by a mission from hour
8 to 10. Earlier `-probe-` runs, including parameter checks, were
diagnostic and excluded from acceptance. These observations cannot
establish the full GAMMA law, general `n`/`Beta` semantics, tail,
independence, universal on-time behavior, GUI-only behavior, other J01
variants or cross-engine parity.
