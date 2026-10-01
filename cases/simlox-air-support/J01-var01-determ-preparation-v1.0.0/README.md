# J01.var01 deterministic preparation distribution

This package tests one catalog `J01.var01` boundary using accepted `B01@1.0.1`
as its exact parent. The sole preparation row keeps mandatory `DURN=0.5` hour
and changes `DURND` from empty to `PREP-DET`. One `TimeDistributions` row
defines `PREP-DET` as `<DETERM>`, `PFAC=1`, `PARAM1=0.5` hour. No preparation
subtasks exist, so the distribution is not overridden by `TaskBreakDown`.

The installed database dictionary defines the column order and native enum.
SIMLOX manual pages 510–511 describe `MissionPreparation.DURN`/`DURND` and
pages 543–545 define `<DETERM>` parameters. Both source hashes are pinned in
`contract.json`. `build.py --check` verifies the exact source input and parent
diff. The guarded SSH runner requires session 0, an `sshd.exe` ancestor, the
host-wide Issue #18 mutex, pinned SIMLOX executable and GUI PID 13340.

The first non-PTY SSH preflight (`-01`) stalled before creating a run directory
or launching SIMLOX and was stopped. The fresh PTY run `-02` completed all four
native stages with zero conversion errors, warnings #108/#126, an exact
13-table business roundtrip, one half-hour preparation and one successful
mission. Its 11 raw artifacts and 9 post-run source hashes are sealed under
ignored `runs/j01-var01-determ-probe-20261001-02/`. `validate.py` replays the
author checks without invoking SIMLOX.

The observed behavior supports this deterministic reference and workload.
It does not establish stochastic distribution behavior, other J01 variants,
or complete Issue #18. Publication requires independent read-only review and
merge to `simlox/main`.
