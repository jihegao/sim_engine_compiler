# C02.var04 explicit subtask resource set

This package freezes a source-bound two-arm SIMLOX CLI experiment. Both arms add P-CREW and E-GSE requirements to the main `PREP-FIXED` task while retaining E-GSE capacity zero. The joint arm repeats both requirements explicitly on `INSPECT` SEQ1. The crew-only arm omits E-GSE from that explicit subtask set. The arms differ only in that removed row and `ProblemDescription.PDESC`.

The [contract](contract.json) pins accepted C02 and C01 source bytes, three accepted run closures and 33 raw file seals. The installed 2017 manual, physical pp. 397–399 and 407–409, states that an explicit subtask resource set replaces the entire main-task set. Accepted C02 had no `TaskResource` rows, so this new pair is required to test omission while a main resource demand exists.

`build.py` creates or byte-checks the exact inputs and `exact-diff.json`; `check_roundtrip.py` checks every authored populated row/column/instance; `validate_native_cli.py` is a predeclared typed-event and full six-table report gate. `self_check.py` tests rejection of source, typed request and report-cell mutations without SIMLOX. `make_prelaunch_manifest.py` seals the source bundle after static checks. `run_native_ssh.ps1 -PreflightOnly` is for a separate authenticated SSH session-0 PowerShell 5 invocation by the controller. A native run requires an independent exact-file prelaunch approval.

The two planned run IDs are `c02-var04-v100-joint-ssh-20261007-01` and `c02-var04-v100-crewonly-ssh-20261007-01`. No native result is accepted yet. The experiment is limited to one fixed-seed aircraft, one INSPECT subtask and CLI evidence; it does not establish a general task-resource or GUI rule.
