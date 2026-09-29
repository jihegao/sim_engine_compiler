# E04.var03 zero-time upstream transport, v1.0.0

This bounded variant derives from [accepted E04 FAST](../E04-upstream-transport-fast-v1.0.0/cli-scope-signoff-2026-09-29.md). The only behavioral changes are `StationStructure.TFRMS=2→0` and `TTOMS=2→0` on the single BASE-01→DEPOT-01 link. The [contract](contract.json) predeclares the inventory, event and report checks; the [parent diff](parent-diff.json) records the exact two-table change, including its descriptive label. The [CLI scope sign-off](cli-scope-signoff-2026-09-30.md) records accepted native evidence and its limits.

Run `python build.py` to verify the frozen input. `python build.py --write` creates it only if absent. Native outputs stay under ignored local `runs/`.
