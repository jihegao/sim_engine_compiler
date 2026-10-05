# I07.var06 first batch above new ROSIZ: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for one later-demand
first reorder batch after a scheduled ROSIZ change. It becomes
`reusable_published` only after merge to `simlox/main`. Full I07 and Issue
#18 remain open; K01/K08 GUI observations remain blocked.

Both arms derive from the accepted E15 explicit-three stock point by
changing initial ROSIZ two-to-three. They retain nominal four, opening
on-hand three, one-hour reorder lead and the same ordinary hour 10 demand.
Only the child has `ChangesStockAllocation` ROSIZ one at hour 5; the control
has an all-null placeholder. The accepted I07.var02 isolation is pinned.
I02 OUT is a catalog prerequisite pin only; no transfer is modeled here.
The installed manual physical pages 516–517 state that a ROSIZ update alone
does not immediately order, and that a first order after the next demand
can exceed the new ROSIZ. Independent reviewers approved the contract and
strict runner before execution.

One unique matched pair completed eight guarded session-0 SSH stages under
`Global\SimloxIssue18NativeQueue`, preserving GUI PID13340/session1. Each
arm passed exact pre-calculation roundtrip of 22 authored populated tables;
conversion gave Errors0/Warnings1 (sole #108)/Notes0. The immutable
closure seals 24 raw files, including SXI/SXO, logs and selected report.

At hour 5 the child ROSIZ changes but neither arm orders or moves stock.
At hour 10 the same ordinary demand takes depot physical ID0, leaving
on-hand two. Control ROSIZ3 has reorder point one and makes no order.
Child ROSIZ1 has point three and starts one two-item order. New physical
IDs5/6 arrive at hour 11, raising depot on-hand to four. ID0 reaches base
at hour 12 in both arms. Every native stock snapshot and all 72 half-hour
depot STSZ/STOHA/NRO/NBO bins reconcile. There is no backorder; mission,
system, summary and aggregate stock report rows match. Author replay passes
**418/418** checks; independent read-only replay is filed separately.

This is one fixed seed, one stock-based discardable DU and one later
ordinary demand. The two-item first batch exceeds new ROSIZ one in this
state only. No general batch algorithm, second order, other initial stock,
transfer, time-based policy, GUI or cross-engine behavior is established.
