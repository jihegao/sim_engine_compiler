# E04.var01 SLOW upstream demand timing, v1.0.0

This bounded accepted CLI variant derives from [accepted E04 FAST](../E04-upstream-transport-fast-v1.0.0/cli-scope-signoff-2026-09-29.md). The only behavioral field change is `StationStructure.OPOL=FAST→SLOW` on the single BASE-01→DEPOT-01 support link. The [contract](contract.json) predeclares the wait for the faulty item to reach the depot before the upstream demand can issue a spare. The [parent diff](parent-diff.json) records the exact two-table change, including the descriptive label. The [dated signoff](cli-scope-signoff-2026-09-29.md) records the native comparison and limits.

Run `python build.py` to verify the frozen input. `python build.py --write` creates it only if absent. Native outputs remain local under ignored `runs/`.
