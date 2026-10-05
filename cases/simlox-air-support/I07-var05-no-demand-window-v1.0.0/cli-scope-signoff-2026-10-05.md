# I07.var05 no-depot-demand interval: bounded source signoff

**Decision:** `native_behavior_accepted_cli_scope` for the source-bound
hour [5,10) observation inside accepted I07.var02 v1.0.1. It becomes
`reusable_published` only after merge to `simlox/main`. No new native run
was made. Full I07.var05, I07 and Issue #18 remain open.

The accepted parent index, contract, signoff, inputs and independent verdict
are byte-pinned in this package's contract. Its original immutable closure
and all 22 raw files are rechecked in place; no raw bytes are duplicated.
The accepted paired source differs only in the child h5
`ChangesStockAllocation.ROSIZ=1` row versus the control all-null row. Both
start with depot nominal/on-hand four and ROSIZ two. The installed manual
physical page 516 says a scheduled ROSIZ change itself does not order; the
next demand or transfer rechecks stock state. The parent run provides a
bounded five-hour interval with neither event at the depot.

Both complete native event logs have no depot item-stock demand,
`ItemTransfer`, reorder start/completion, delivery or physical depot stock
move during [5,10). All ten selected depot half-hour bins in each arm show
STSZ4/STOHA4/NRO0/NBO0. The first depot item demand is at hour 10 and
issues physical ID0; only the child then orders one, as published under
I07.var02. The interval has other mission/system activity, including a
mission request at hour 7 and a component failure at 9.8829.

Author source replay passes **114/114** checks. Its first pass used 14 as
the expected published source-file count, while the parent index has 15;
the failed checker report is preserved under `review/`. The corrected
checker and independent read-only interval replay use the original parent
raw and published source pins without changing them.

The scheduled h5 parameter application is not separately printed in the
native event log; the source row and later h10 child-only order bind this
interpretation. This does not claim a full-horizon no-demand run, an
indefinite absence of orders, other stock states, transfer behavior, GUI,
cross-engine equivalence or full I07.var05 acceptance.
