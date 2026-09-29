# A17 native probe preflight, 2026-09-29

This record preserves the early preflight failures and their resolution.
The model is now a native CLI candidate; the dated sign-off controls any
later publication decision.

The first two SSH launches (`a17-v100-schema-probe-20260929-01` and `-02`)
stalled before run-directory creation because the probe helper reused
PowerShell's automatic `$input` variable as a path. The own session-0
PowerShell helpers were stopped after confirming that no native child process
existed; GUI PID 13340 was not stopped or restarted. The helper now uses
`$nativeInputPath` and passed a read-only SSH preflight diagnostic.

The corrected launch (`a17-v100-schema-probe-20260929-03`) exited 1 at the
active-GUI-session guard. `qwinsta` reported session 1 as `Disc`, while GUI
PID 13340 remained present in that session with its original start time.
This guard ran before creating the run directory or invoking SIMLOX. It is an
environment preflight failure, not evidence that the model imports or fails
to import. No GitHub Actions or native behavior conclusion follows.

The GUI session later became active while PID 13340 retained its original
start time. The `-04` probe imported and exported the model; SIMLOX added
18 populated built-in default tables on export while preserving all 15
source tables with rows, including three all-null placeholders. The initial checker incorrectly
required exact table-name equality, so the immutable `-04` closure records
`probe checker exit=1`. A corrected checker replayed the raw `-04` files
read-only and passed, while leaving the original failed closure intact.

The separate four-step run `a17-v100-ssh-20260929-01` then imported,
exported, calculated and exported a JSON report with all commands exiting
zero under session-0 SSH. Its copied input SHA-256 remained
`66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974`,
and the GUI PID/start identity was preserved. The native calculation log
records zero conversion errors and warnings 108/126. Its author validator
passed 281 checks; separate read-only replay also passed, and the
[dated sign-off](cli-scope-signoff-2026-09-29.md) records the bounded
publication decision.
