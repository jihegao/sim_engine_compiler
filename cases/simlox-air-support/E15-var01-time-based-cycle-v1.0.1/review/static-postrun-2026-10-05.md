# E15.var01 time-cycle report extension: independent post-run audit

**GO, bounded to one initial 16-hour cycle and this fixed model.** The
v1.0.0 run remains an excluded diagnostic because its frozen converter
warning gate expected `ItemReorder` rather than the actual
`StockAllocation` record-2 #376. This extension reads that run's sealed
SXO without recalculating it.

The new closure SHA-256 is
`e194863a14e889630bfda165b8394e737a42536fe8d55b0507b0c9703d6e16a6`.
I independently verified all four new and eleven original raw file
size/SHA seals, both invocation hashes, and all 15 literal pins plus
runner and Python against the new closure's before and after source
maps. The closure error is null. The single hidden report step recorded
session-0 SSH with an `sshd.exe` ancestor, the global native mutex,
protected GUI PID 13340/session 1/start identity, GUI preserved, and
exit 0. Its only native operation was `-report -rpts -rjexport` from the
original sealed SXO; no calculation, model import/export or save was run.

The selected report is 210,308 bytes, SHA-256
`d41c5d0a17e0456453f24bd2c142c2c2c84095ec7e65e7a7e5fdaffdc373c1e0`.
It has the same ten tables and columns as the accepted E15 default-on-hand
selected report. Both have 72 half-hour ItemResults rows for
`TEACH-DU-01` at `DEPOT-01`. A cell-by-cell comparison found exactly
39 changes in ItemResults, only `STOHA` and `NRO`, and two changes in
ItemResultsTotal, again `STOHA` and `NRO`. All eight other tables,
including ResultSummary, Mission, System and StockTotal results, match
cell-for-cell. ItemResultsTotal mean `STOHA` is about 3.80556 in the
child versus 3.27778 in the accepted parent; `NRO` is 1 versus 0.

Child `STSZ` is 4 in every depot bin. `STOHA` is 4 before h10, 3 from
h10 through the h16.5 bin, and 4 from h17 through terminal h36. `NRO`
is 1 only in the h16 bin, and `NBO` is zero throughout. The original
complete event log independently records depot physical ID0 issued at
h10, its BASE-01 arrival at h12, no h10 depot reorder, one-item reorder
started h16, and new ID6 delivered h17; depot stock returns to four.
The accepted parent has no such order. The selected ItemResults covers
the depot; BASE-01 physical identity comes from the event log.

This establishes the observed initial time-based order at h16 and
one-hour receipt in this DU/depot/seed model with `ROINT=16`. It does
not establish other intervals, repeated demand, strategy changes,
different items or stations, GUI behavior, cross-engine parity, or full
E15.var01 coverage.
