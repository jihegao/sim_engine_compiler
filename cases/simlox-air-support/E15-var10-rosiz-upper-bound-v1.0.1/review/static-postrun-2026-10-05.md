# E15.var10 warning/report extension: independent post-run audit

**GO, bounded to this invalid depot stock row and one fixed run.** The
v1.0.0 converter-error contract remains an excluded diagnostic. This
v1.0.1 extension reports from its sealed SXO and supports a narrower
warning-plus-observed-stock result.

The new closure SHA-256 is
`a4adc00d8c44cba5e9ed41d1272a8c9f510a96dfb6d881a2dccc5ff74b2e202a`.
I independently checked all four new and eleven old raw files against
their closure sizes and SHA-256 values, both invocation hashes, and every
current source hash. The 15 literal pins plus runner and Python match the
new closure's before and after maps. Its error is null. The old closure
still records `expected converter error absent`; its log reports Errors 0,
Warnings #108 and #168, Notes 0, and the exact StockAllocation record-2
warning `Reorder size too large (ROSIZ > STSIZ+1): TEACH-DU-01`.

The new invocation records session-0 SSH with an `sshd.exe` ancestor,
`Global\SimloxIssue18NativeQueue`, and protected GUI PID 13340/session 1
with its pinned start time. The sole GUI-preserved hidden step exited zero
and used `-report -rpts -rjexport` on the old sealed SXO. The export log
confirms completion. No calculation, model import/export, or save command
was run in this extension.

The selected child JSON report is 210,362 bytes, SHA-256
`09cd76ba9da91ec32ba37ae27610bc3ea42a962f5030a8a4fb9e92fbfae4b615`.
It has the same ten tables and columns as the accepted E15 explicit-three
selected report, including 72 half-hour ItemResults rows for
`TEACH-DU-01` at `DEPOT-01`. ProblemDescription, ResultSummary, Mission,
FixedMission, System and StockTotal tables match the accepted report
cell-for-cell. ItemResults differs in `NRO` at h10 (child 0, accepted 1)
and `STOHA` from h11 through h36 (child 2, accepted 4). The corresponding
ItemResultsTotal values also differ: mean `STOHA` about 2.27778 versus
3.66667 and `NRO` 0 versus 1. Both reports have `NBO` 0 throughout.

The old sealed event log starts with depot physical IDs 0/1/2 and one
BASE-01 item. At h10 depot ID0 is issued toward BASE-01, leaving depot
IDs1/2; the same ID reaches BASE-01 at h12. Unlike the accepted log, the
child log contains no depot reorder task or later two-item delivery.
Thus the report's depot on-hand 3 before h10 and 2 afterward matches the
physical ledger. The selected ItemResults is depot-specific; BASE-01
identity is supported by the complete event log.

This establishes that this installed CLI warned #168 yet simulated one
`STSIZ=4`, `ROSIZ=6` discardable stock-based depot row without a reorder
after the h10 issue. The input exceeds the documented bound. It is not
evidence that excess ROSIZ is a supported stock policy or that other
invalid sizes, stations, items, seeds or engines behave alike.
