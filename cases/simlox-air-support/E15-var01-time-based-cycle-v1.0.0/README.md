# E15.var01 v1.0.0 excluded diagnostic

A single reviewed SSH session-0 native run tested depot ItemReorder.ROINT 0 to 16 hours against accepted E15.var07 default on-hand stock. Its 21-table round trip passed, and SIMLOX produced a valid result, but the frozen gate required a row-specific ItemReorder warning. The installed converter emitted #376 under StockAllocation rec 2 with the exact item and depot instead. This version remains excluded; no gate was revised after the run.

The sealed event log observes h10 issue of physical DU ID0, no h10 reorder, h16 reorder task, h17 one-item delivery of new ID6, and depot restoration from three to four. These observations informed a separately reviewed v1.0.1 report-only extension, without recalculation. The original run directory remains local and immutable. No GUI-specific or cross-engine behavior is claimed.
