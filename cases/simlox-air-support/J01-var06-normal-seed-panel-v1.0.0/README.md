# J01.var06 normal preparation distribution

This package tests catalog variant `J01.var06` against the accepted
`J01.var01@1.0.0` input. Seed 01 changes only `MissionPreparation.DURND`
from `PREP-DET` to `PREP-NRM` and its `TimeDistributions` row to
`PREP-NRM`, `PFAC=1`, `BASED=<NORMAL>`, `PARAM1=0.5` mean and
`PARAM2=1.0` standard deviation. Mandatory `DURN=0.5` hour remains.
Seeds 02–12 differ from seed 01 only in `Control.RSEED`; all have
`NREPS=1`. Run `build.py --check` to verify the inputs and panel diff.

The installed database dictionary permits `<NORMAL>` and the installed
manual pp. 542–545 define its mean and standard deviation parameters
and a zero lower boundary. Native import/export retained the input row.
Proprietary sources are pinned by SHA-256 in `contract.json` and are
not included here.

Run each seed through `run_native_ssh.ps1` in an authenticated session-0
SSH connection with a PTY, fresh `-RunId`, matching `-Seed` and
`-InputSha256` from `panel-diff.json`, and `-AllowExistingGui`. The
runner checks GUI PID 13340 and its start identity, native executable,
source hashes and the host-wide Issue #18 mutex. It seals partial raw
evidence after a failed step. `validate.py RUN_DIRECTORY SEED` replays
one run without SIMLOX; `validate_panel.py` checks all twelve accepted
runs. Ignored local `runs/` folders and raw SHA-256 seals are indexed
in `evidence-index.json`.

The accepted fixed seeds have four exactly zero preparation durations
and three durations exceeding the one-hour notice. Delayed missions
launch at preparation completion and succeed about two hours later.
Earlier `-probe-` runs were diagnostic and excluded. These observations
cannot identify the generator's mathematical truncation method or prove
the population law, tail, independence, GUI-only behavior, other J01
variants or cross-engine parity.
