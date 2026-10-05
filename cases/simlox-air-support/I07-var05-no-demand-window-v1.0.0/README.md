# I07.var05 — demand-free depot interval after ROSIZ change

This is a source-bound mapping of the accepted I07.var02 v1.0.1 matched
run, not a new native simulation. The accepted child schedules ROSIZ two
to one at hour 5; the matched control has an all-null change placeholder.
Both have nominal and opening depot on-hand stock four.

From hour 5 until hour 10, neither arm has a **depot item-stock demand or
transfer**. The event logs show no depot stock movement, reorder or
delivery in that interval. All ten selected half-hour depot `ItemResults`
rows per arm retain STSZ4, STOHA4, NRO0 and NBO0. The first ordinary depot
item demand occurs at hour 10; only the child then starts an order, as
already accepted under I07.var02. The h5 scheduled application is not
printed as a distinct native event.

The package checks the original published source, closure and all 22 local
raw seals without copying or changing them. It records an author replay
and a separate read-only review of this narrower interval. One author
checker first pass used an incorrect source-file count; its diagnostic
report is preserved. The corrected checker uses the actual 15 published
source pins and leaves all accepted evidence untouched.

The run continues after hour 10, so this does not establish a 36-hour
simulation without depot demand. A mission activates at hour 7 and a
component fails at hour 9.8829; “no demand” here means no new demand at
the depot item-stock point. This mapping does not complete full catalog
I07.var05, GUI behavior, cross-engine equivalence or Issue #18.
