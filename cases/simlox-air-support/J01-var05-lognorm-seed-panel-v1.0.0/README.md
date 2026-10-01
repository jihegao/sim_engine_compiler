# J01.var05 lognormal preparation distribution

This package tests catalog variant `J01.var05` against the accepted
`J01.var01@1.0.0` input. Seed 01 changes only `MissionPreparation.DURND`
from `PREP-DET` to `PREP-LGN` and its `TimeDistributions` row to
`PREP-LGN`, `PFAC=1`, `BASED=<LOGNORM>`, `PARAM1=0.5` location and
`PARAM2=0.25` scale. Mandatory `DURN=0.5` hour remains; the location
parameter is not presented as the preparation mean. Seeds 02–12 differ
from seed 01 only in `Control.RSEED` and all have `NREPS=1`. Run
`build.py --check` to verify all inputs and `panel-diff.json`.

The installed database dictionary lists the native `<LOGNORM>` enum.
The installed manual pp. 542–545 prints `<LOGNORMAL>` and assigns
`PARAM1` and `PARAM2` to location and scale. Native import/export
accepted and retained `<LOGNORM>` with those values. Source hashes are
pinned in `contract.json`; proprietary sources are not included here.

Run each seed using `run_native_ssh.ps1` in an authenticated session-0
SSH connection with a PTY, fresh `-RunId`, matching `-Seed` and
`-InputSha256` from `panel-diff.json`, and `-AllowExistingGui`. The runner
checks GUI PID 13340 and its start identity, native executable, source
hashes and the host-wide Issue #18 mutex. It seals partial raw evidence
after a failed step. `validate.py RUN_DIRECTORY SEED` replays one run
without SIMLOX; `validate_panel.py` checks all twelve accepted runs.
Ignored local `runs/` folders and raw SHA-256 seals are indexed in
`evidence-index.json`.

The twelve accepted seeds had positive, distinct preparation durations
within the one-hour notice, followed by a mission from hour 8 to 10.
Earlier `-probe-` runs were diagnostic and excluded from acceptance.
These fixed-seed observations do not prove the population law, tail,
independence, a general lack of notice overrun, GUI-only behavior, other
J01 variants or cross-engine parity.
