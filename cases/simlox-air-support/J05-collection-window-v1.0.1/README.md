# J05.var01–02: global and SYSTEM result windows

This bounded case derives three inputs from accepted [A01](../A01-single-aircraft-single-mission/native-input.json): an unchanged baseline, a `Control` collection window of 7.5–9 hours at 0.25-hour intervals, and the same global window with a `SYSTEM` `ResultCollection` override of 0–36 hours at 0.5-hour intervals. `SIMPE=36`, seed 1, the one-aircraft mission, and all behavior tables are unchanged. The [contract](contract.json) and [exact diff](exact-diff.json) freeze the comparison.

The [CLI scope sign-off](cli-scope-signoff-2026-10-01.md) accepts the observed global System and Stock result windows and the SYSTEM-specific override relative to Stock. The mission starts at 8 and succeeds at 10 in all runs; the short collection window does not stop it. The author replay passes 44/44 checks and a separate read-only replay passes 69/69. Raw native evidence remains sealed in ignored `runs/`.

The installed `-jsonreport` output has no `MissionResults` interval table. Direct MISSION collection override, snapshots, collection profiles, other result types, GUI display and cross-engine equivalence remain unverified. An earlier v1.0.0 diagnostic triplet posed a MISSION interval requirement that its report could not satisfy; those runs are excluded from this publication.
