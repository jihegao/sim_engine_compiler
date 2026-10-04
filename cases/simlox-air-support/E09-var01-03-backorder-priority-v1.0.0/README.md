# E09 v1.0.0 excluded diagnostic

This three-arm native run is retained as a reproducible diagnostic, not a published Issue #18 case. It compares `Control.ENBOP=Y` with depot `Station.BOPRI=N/Y`, plus `ENBOP=N, BOPRI=Y`. The event logs demonstrate concurrent depot requests and opposite allocations of the first repaired LRU. The original contract also required per-station item stock and backorder reports. Its default JSON reports did not emit `ItemResults`, so the full gate failed.

The guarded run is `runs/e09-backorder-priority-v100-ssh-20261004-01` (local, ignored). Its closure SHA-256 is `be24943da186459639a309db3ed3bd8f9bd29744ce3f6fd636f793c7bdfea28e`. The independent diagnostic replay passed 1,352 checks but returned `NO_GO_FULL_CONTRACT` in `review/independent-verdict.json`. This package has no publication-index entry.

The separately versioned `E09-var01-03-backorder-priority-v1.0.1` adds tracked ITEM collection and station-selected report exports, then repeats the guarded native run. It is evaluated under its own contract and seals.
