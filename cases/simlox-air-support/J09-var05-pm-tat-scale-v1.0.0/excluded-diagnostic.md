# J09.var05 v1.0.0 excluded diagnostic

**Disposition:** excluded from positive publication. The guarded native run `j09-var05-scpmt2-v100-ssh-20261004-01` completed import, export, calculation, report and populated-table roundtrip with zero conversion errors, expected warnings #108/#126, and preserved GUI PID 13340. Its [local sealed closure](runs/j09-var05-scpmt2-v100-ssh-20261004-01/closure.json) has SHA-256 `f3af6909873ee2a7a6563aad7d7864cb81260893d25e3498743d2d9c9aa461f4`; raw artifacts remain ignored under `runs/`.

The native `model.log` is byte-identical to accepted D03 (`edd41c34046fb92e53a3f5eb8569cec3a932aa00aed8e878ecc40ef45826a4a5`). The native JSON report is also byte-identical (`a9cc414e9b40da06be620e5fb64c52e0db41ec6fe959ac0874497d358232a84e`). The CAL24 PMs still run 24–25 and 49–50 hours. There is no positive `SCPMT=2` observation.

Installed SIMLOX manual physical page 237 says `SCPMT` applies to `PMLocation.PMT`. Page 389 says PMT is overridden when subtasks are specified. D03 references `PM-CAL24` in `PMLocation.TID`, whose `TaskBreakDown.DURN=1` sets the work duration. The matched task-free control and scaled experiment is prepared separately in `J09-var05-pmt-fallback-pair-v1.0.1`. This v1.0.0 input and its result must not appear as an accepted J09.var05 publication index entry.
