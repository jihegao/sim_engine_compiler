# I07.var02 ROSIZ: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for one scheduled change
of stock-based reorder size at the existing depot point. It becomes
`reusable_published` only after merge to `simlox/main`. The catalog's full
I07 contract and Issue #18 remain open.

The accepted E02, E15 v1.0.1 default arm, and I02 IN/BETWEEN prerequisite
inputs and signoffs match the pins in `contract.json`. The installed 2017
manual, dictionary and executable match the contract bytes. The exact paired
input difference is the six-column `ChangesStockAllocation` row: an all-null
control versus `AIR_BASIC,TEACH-DU-01,DEPOT-01,5,1,null` in the change arm.
The old v1.0.0 explicit-three draft was not run and is not a published failure.

Two independent pre-run reviews approved the frozen contract and guarded
runner. The run `i07-var02-rosiz-v101-ssh-20261005-01` completed eight serial
session-0 SSH native stages under the global mutex while GUI PID 13340 stayed
responsive. Both arms have zero converter errors, one inherited #108 warning,
zero notes, exact roundtrip of all 22 authored populated tables, nonempty
native SXO/event/selected report, and 22 byte-sealed raw files total. The
native export also contains null placeholder rows.

At h5 the scheduled row alone produces no order or physical stock movement.
The common h10 demand issues physical DU ID0 from depot to base, lowering
depot on-hand four to three; that item reaches base at h12 in both arms.
Control ROSIZ two leaves the reorder point at two and starts no order. The
child ROSIZ one sets the point at three, starts one one-unit order at h10,
and receives distinct physical DU ID6 at depot h11. The order size was a
native observation, not assumed from the new ROSIZ. Full event stock
snapshots and each of 72 half-hour selected depot bins reconcile: nominal
STSZ four in both, no backorder, NRO zero versus one, terminal on-hand three
versus four. Mission, system and aggregate StockTotal results agree across
arms; no improved-readiness claim follows.

The author replay passes 406/406 checks. A separate static audit rehashed
all 22 raw files and confirmed the event and selected-report ledger. An
independent read-only raw replay passes 3,476/3,476 checks, including all
source/closure seals, authored-table roundtrips, event differences and 72
selected depot bins. The control native event log is byte-identical to the
accepted E15 default-arm log. The internal reorder-point calculation is not
printed; attribution to the h5 row is a source-bound inference from the
matched pair and the child-only h10 reorder.

This acceptance is limited to one fixed seed, one discardable tracked DU,
one existing stock-based depot point, a h5 ROSIZ two-to-one change, one h10
demand and a 36-hour horizon. It does not establish time-based reorder,
multiple or outstanding orders, tie-time changes, random lead, other
stations or seeds, GUI-only behavior, cross-engine equivalence or full I07.
