# I07.var06 — first reorder batch after a scheduled ROSIZ change

This fixed-seed matched pair uses the accepted E15 explicit-three depot
stock model. Both arms have nominal stock four, opening on-hand three,
initial ROSIZ three and a one-hour reorder lead. Only the child schedules
ROSIZ one at hour 5. The accepted I07.var02 isolated ROSIZ scope is a pinned
prerequisite; accepted behavior was not rerun. No `ItemTransfer` is present
in this pair.

The hour 5 change alone causes no order or stock move. A shared ordinary
hour 10 demand sends physical depot DU ID0 to base, where it arrives at
hour 12; depot on-hand falls from three to two. Control starts no order.
The child starts its first order at hour 10 and receives two physical DUs,
IDs5/6, at hour 11. Thus this observed first batch of two exceeds the new
ROSIZ of one; the batch size was read from the native event and physical
stock ledger. Control finishes with depot IDs1/2; child finishes with
IDs1/2/5/6. There is no backorder in either arm and mission/system results
match.

The guarded session-0 SSH run sealed 24 local raw files while preserving
GUI PID13340/session1. Both arms passed exact pre-calculation roundtrip of
22 authored row-containing tables and conversion Errors0/Warnings1
(sole #108)/Notes0. The author replay and independent read-only review
check all physical stock snapshots and 72 selected depot half-hour
STSZ/STOHA/NRO/NBO bins per arm. Native SXI/SXO/log/report bytes remain in
ignored `runs/`, pinned by `evidence-index.json`.

This result covers one later ordinary demand at one stock-based discardable
DU point. It does not establish a general reorder batch formula, repeated
orders, other opening stocks, transfers, time-based policy, GUI behavior,
cross-engine equivalence, full I07 or overall Issue #18 completion.
