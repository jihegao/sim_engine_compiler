# I07.var10 report-only extension: independent static review

**Verdict: GO, bounded to the frozen existing BASE-01 stock row.** The
v1.0.0 calculation remains an excluded strict-warning-gate diagnostic; this
v1.0.1 run adds one reviewed report export from its sealed child SXO. It does
not recalculate or change the model.

I independently rehashed all 22 v1.0.0 raw files and all four v1.0.1 raw
files against their respective closure byte sizes and SHA-256 values. Both
invocation hashes match their closures. The v1.0.1 closure SHA-256 is
`30091521923b20d2ccdd5b8ea1e0505e7c89ada92d2e156fe810d8d42b17ea88`;
its error is null, and all 15 pinned source hashes match the current files
and the closure's identical before/after maps. The v1.0.0 closure still has
the explicit `change unreviewed converter diagnostic` error. Its child
converter log reports Errors 0, Warnings 2, Notes 0, specifically #108 and
the row-specific #172, “No reorder data defined. ROSIZ ignored.
TEACH-DU-01 / BASE-01”.

The new invocation records session 0, an `sshd.exe` ancestor, the global
native queue mutex, and protected GUI PID 13340 in session 1 with the pinned
start time. Its sole guarded step preserved that GUI, exited 0, and used
`-report -rpts -rjexport` on the sealed child SXO. The report export log
confirms completion. The command contains no import, calculation, model
export, or save operation. The runner SHA-256 captured by this run is
`fa07f883d1fc9e83324ac35ec49331e7b50385cb5c0af08abbc56aa93075bd35`.

The new child report is 210,302 bytes, SHA-256
`e56a2de326bf91f50d6155f5a81ed5f881fa352e2aebb62e804564dbb3536405`.
It is **byte-identical** to the original control report. Both contain the
same ten tables, including 72 half-hour DEPOT-01 ItemResults rows. The
complete paired event logs are also byte-identical. Their physical snapshots
start with one BASE-01 item and three DEPOT-01 items; the first demands and
issues occur at h10, the depot reorder receipt at h11, and the BASE-01
receipt at h12. No h5 BASE order or stock movement is logged. The selected
ItemResults covers DEPOT-01; BASE-01 stock identity comes from the complete
event logs, not from an unreported BASE ItemResults table.

This supports the contract's ignored-value observation for an h5 ROSIZ
change on this existing BASE-01 StockAllocation row without a matching
BASE ItemReorder row. It does not establish behavior for absent stock rows,
other item or station types, other times, GUI execution, or all I07.var10
configurations.
