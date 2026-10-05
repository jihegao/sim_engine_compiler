# I07.var03 — a lead-time change while an order is outstanding

This case reuses the accepted I07.var01 h5 `ChangesItemReorder.LEADT` input,
moving only its change time to h10.5 (and changing the description). The
existing stock-based DU order starts at h10 under initial LEADT one hour.
The late change sets LEADT three hours while that order is pending. The
accepted h5 comparator starts an otherwise matched order after its change.
Only the late arm has a new native run; accepted cases were not rerun.

The pending order retains its original schedule: it delivers two new DU
items, IDs 5 and 6, to the depot at h11. The accepted early-change order
has a three-hour lead and delivers at h13. Both runs issue physical ID0 from
depot to base at h10; it reaches base h12. The late depot has three on hand
initially, two from h10 until h11, then four. The early comparator stays
at two until h13. Both have one order, no backorder, and the same mission,
system and aggregate stock results.

The native log does not separately announce application of the h10.5 row.
This pair supports a bounded conclusion about the existing order's retained
delivery time. It does not exercise a later order to show its use of the new
LEADT value. `build.py` reconstructs the byte-pinned input; the guarded
session-0 runner gates exact 22-table roundtrip before calculation and seals
all raw files under one immutable run ID. `validate.py` and an independent
read-only replay verify the physical/event ledger and all 72 selected depot
half-hour bins. Native SXI/SXO, logs and reports remain in ignored `runs/`.

Scope: one fixed seed, one existing depot order, one mid-order LEADT change.
No time-based ROINT cycle, second order, tie-time update, random lead, GUI,
cross-engine or full I07/Issue #18 conclusion is established.
