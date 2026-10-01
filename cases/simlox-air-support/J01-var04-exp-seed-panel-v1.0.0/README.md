# J01.var04 exponential preparation distribution

This package tests catalog variant `J01.var04` against the accepted
`J01.var01@1.0.0` input. Seed 01 changes only `MissionPreparation.DURND`
from `PREP-DET` to `PREP-EXP` and its `TimeDistributions` row to
`PREP-EXP`, `PFAC=1`, `BASED=<EXP>`, `PARAM1=0.5` mean hour, with
`PARAM2` and `PARAM3` empty. Mandatory `DURN=0.5` hour remains. Seeds
02–12 differ from seed 01 only in `Control.RSEED`; all have `NREPS=1`.
Run `build.py --check` to verify all inputs and `panel-diff.json`.

The installed database dictionary lists the native `<EXP>` enum. The
installed manual p. 511 also allows `<EXP>` directly as a preparation
distribution, while its general parameter table on pp. 543–545 spells
the exponential base `<NEGEXP>` and assigns `PARAM1` its mean. Native
import/export accepted and retained `<EXP>` in the tested row. Source
hashes are pinned in `contract.json`; proprietary sources are not
included here.

Run each seed using `run_native_ssh.ps1` in an authenticated session-0
SSH connection with a PTY, fresh `-RunId`, matching `-Seed` and
`-InputSha256` from `panel-diff.json`, and `-AllowExistingGui`. The
runner checks GUI PID 13340 and its start identity, the native executable,
source hashes and the host-wide Issue #18 mutex. It seals partial raw
evidence after a failed step. `validate.py RUN_DIRECTORY SEED` replays a
run without calling SIMLOX; `validate_panel.py` checks all twelve runs.
Ignored local `runs/` folders and their raw SHA-256 seals are indexed in
`evidence-index.json`.

An exponential draw can exceed the one-hour mission notice. In the
frozen panel seed 09 takes 1.07748 hours from hour 7; its mission starts
at preparation end near hour 8.07748 and succeeds near 10.0775. The
other eleven start at hour 8 and succeed at hour 10. Earlier runs under
`-probe-` IDs were diagnostic and are excluded from acceptance. These
fixed-seed observations do not prove the population law or full tail,
independence, a universal delayed-start rule, GUI-only behavior, other
J01 variants or cross-engine parity.
