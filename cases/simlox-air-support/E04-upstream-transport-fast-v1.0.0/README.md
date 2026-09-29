# E04 FAST upstream stock and fixed transport, v1.0.0

This bounded accepted CLI case derives from [accepted E02](../E02-zero-stock-local-backorder-v1.0.0/cli-scope-signoff-2026-09-29.md), with the accepted [A17 explicit-station prerequisite](../A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md). Base stock remains zero. One spare starts at `DEPOT-01`, connected to `BASE-01` through a general `StationStructure` link with FAST ordering and two-hour shipment each way. Local direct LRU repair moves to the depot so the first shortage exercises the upstream route. The [contract](contract.json) predeclares the separate demand and faulty-item paths; the [parent diff](parent-diff.json) lists the five changed tables. The [dated signoff](cli-scope-signoff-2026-09-29.md) records observed scope and limits.

Run `python build.py` to verify the frozen input. `python build.py --write` creates it only if absent. Native outputs stay under ignored `runs/` and are not distributed.
