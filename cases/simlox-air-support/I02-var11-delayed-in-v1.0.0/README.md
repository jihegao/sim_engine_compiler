# I02.var11 — positive-duration scheduled IN

This bounded case changes only `ItemTransfer.TFDT` from 0 to 2 hours in the
accepted I02.var01 one-unit `<OUTSIDE>` to `DEPOT-01` transfer at hour 4.
`ProblemDescription` identifies the child; the other 30 tables are unchanged.
The installed manual describes TFDT narrowly in one section and explicitly
allows it for IN in its field definition, so the timing is determined here by
native output rather than by either wording alone.

`build.py` and `describe_diff.py` freeze the source and table delta. The guarded
`run_native_ssh.ps1` executes SIMLOX under the session-0 queue and checks all
22 populated authored tables after import/export. `make_report_settings.py`
recreates the local depot item selector from the fingerprinted installed
default. `report_native_ssh.ps1` exports ItemResults from the sealed SXO
without recalculation. Native files and the proprietary selector remain under
ignored `runs/`; `evidence-index.json` seals their local paths and hashes.

The native log records the scheduled task starting at hour 4 and physical
item ID 1 arriving at depot at hour 6. Depot `ItemResults.STSZ` and `STOHA`
stay at 1 through hour 5.5, then rise to 2 at hour 6. Exactly four half-hour
rows from hour 4 to 5.5 differ from the accepted zero-duration parent, and
only those two stock columns differ. Later demand, repair, mission and system
observations match the parent. `validate_native.py` and the independent
checker under `review/` replay source, closures, raw evidence and contrast.

The claim is limited to one IN, one item and depot, TFDT 0 versus 2, seed 1,
and this installed CLI. It does not establish other delay values, OUT,
BETWEEN, shortages, reorder or procurement, GUI rendering or cross-engine
behavior.
