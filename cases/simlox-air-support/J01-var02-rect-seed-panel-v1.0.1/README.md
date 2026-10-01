# J01.var02 rectangular preparation distribution

This package tests the frozen catalog's `J01.var02` boundary against accepted
`J01.var01@1.0.0`. Seed 1 changes only the preparation's `DURND` reference and
its `TimeDistributions` row to `PREP-RCT`, `PFAC=1`, `BASED=<RECT>`,
`PARAM1=0.25`, `PARAM2=0.75` hour. The mandatory `DURN=0.5` hour remains.
Seeds 2–12 differ from seed 1 only in `Control.RSEED` and have `NREPS=1`.
`build.py --check` verifies the exact inputs and `panel-diff.json`.

The installed database dictionary supplies the native `<RECT>` enum and
column order. SIMLOX manual pages 510–511 describe preparation distributions;
pages 543–545 define the lower and upper RECT parameters. The manual's p544
`<IRECT>` spelling conflicts with its p543 table and the installed dictionary;
the native input uses the dictionary's `<RECT>` value. Their file hashes are
pinned in `contract.json`.

Each seed is run through `run_native_ssh.ps1` using a fresh run ID, the
matching input SHA-256 from `panel-diff.json`, `-Seed N`, and
`-AllowExistingGui`, inside an authenticated session-0 SSH call with a PTY.
The runner checks the SIMLOX executable, GUI PID 13340 and start identity,
host-wide Issue #18 mutex, input and source hashes; it seals raw output even
on a failed native step. `validate.py RUN_DIRECTORY SEED` replays a run without
calling SIMLOX; `validate_panel.py` replays all twelve runs and checks the
sample panel. Native raw files remain in ignored `runs/` and are listed by
hash in `evidence-index.json`.

An earlier 40-repetition diagnostic in the separate local
`J01-var02-rect-preparation-v1.0.0` folder showed that native `model.log`
contains only one visible timeline even when `ResultSummary.NREP=40`.
That pair is excluded from this seed-panel acceptance. Twelve distinct seed
runs provide twelve visible preparation durations, descriptive statistics,
and matched event/report reconciliation. The panel cannot prove a population
distribution law or endpoint attainment; other J01 variants remain open.
