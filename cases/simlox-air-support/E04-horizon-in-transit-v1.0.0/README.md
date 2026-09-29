# E04.var04 upstream spare in transit at simulation end, v1.0.0

This variant derives from [accepted E04 FAST](../E04-upstream-transport-fast-v1.0.0/cli-scope-signoff-2026-09-29.md). The only behavioral input change is `StationStructure.TFRMS=2→30` hours on its sole BASE-01→DEPOT-01 support link; the normal 36-hour horizon remains. The [contract](contract.json) predeclares physical item, report and terminal-state checks, and the [parent diff](parent-diff.json) records the two-table change including its descriptive label. The [CLI scope sign-off](cli-scope-signoff-2026-09-30.md) records accepted evidence and its inference limits.

Run `python build.py` to verify the frozen input. `python build.py --write` creates it only if absent. Native outputs stay under ignored local `runs/`.
