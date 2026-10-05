# Independent postrun review: E15.var07 v1.0.2

**Decision: PASS, bounded to this source and sealed run.** The separate standard-library replay passes **2,190/2,190** checks. Two consecutive executions produced the same verdict SHA-256, `29460deb965f2c3a132d891c3ae1d55a9fe31baec4d08650b76602beb9c473fc`.

The child changes only depot `StockAllocation.ISTOH` from 3 to 5 relative to accepted v1.0.1. The run closure SHA-256 is `15d7d85c1fb2d2612bb8a4ce6b446e161e6974b0640db0ec6f2787e381cbdd3d`. All 13 raw files match their SHA-256 and size seals; source hashes match before and after. The guarded session-0 run retained GUI PID 13340, completed four native steps, preserved all 21 authored row-containing tables on import/export, and converted with Errors 0, Warnings 1 (only #108), Notes 0 and a usable SXO.

The native log opens the depot with physical DU IDs 0–4 (five on hand), alongside base spare ID 5 and installed item ID 6. Item 6 fails at h9.8829, aborting the first mission. At h10 base spare 5 is issued and depot item 0 is issued, leaving depot IDs 1–4 (four on hand); item 6 is discarded at h10.1667. The aircraft is ready at h10.5; item 0 arrives at BASE-01 at h12. The h20 and h32 missions succeed, and the aircraft is ready at the horizon. No reorder task or delivery is logged in this 36-hour run.

All 72 depot `ItemResults` half-hour rows independently reconcile: `STSZ=4`, `NBO=0`, `NRO=0`; `STOHA=5` before the h10 issue and `STOHA=4` thereafter. `ItemResultsTotal` reports mean on-hand 4.2777776718 and NRO 0. The eight other selected tables are row-identical to accepted v1.0.1, including mission, system, stock-total and summary results. Relative to that parent, the 72-bin item table changes only 22 `STOHA` cells and the h10 `NRO` cell; the item-total table changes only mean `STOHA` and `NRO`. The physical IDs differ because the child opens with two extra units; no event-log byte-parity claim is made.

This accepts the observed above-nominal opening stock (`ISTOH=5`, `STSIZ=4`) and its first demand for one seed and one depot. It does not establish a universal nominal-stock cap, later-demand reorder behavior, or population behavior.
