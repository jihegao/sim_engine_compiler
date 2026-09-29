# E04.var02 upstream shortage under FAST ordering, v1.0.0

This bounded variant derives from [accepted E04 FAST](../E04-upstream-transport-fast-v1.0.0/cli-scope-signoff-2026-09-29.md). Only DEPOT-01 initial LRU stock changes from one to zero. The [contract](contract.json) predeclares the alternative native outcomes, event and report checks; the [parent diff](parent-diff.json) records the exact two-table change, including its descriptive label. The [CLI scope sign-off](cli-scope-signoff-2026-09-30.md) records the accepted native behavior and its limits.

Run `python build.py` to verify the frozen input. `python build.py --write` creates it only if absent. Native outputs stay under ignored local `runs/`.
