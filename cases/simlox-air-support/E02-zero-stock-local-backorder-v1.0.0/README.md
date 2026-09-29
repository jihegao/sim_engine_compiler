# E02 zero local stock and repair-served backorder, v1.0.0

This bounded accepted CLI case derives from [accepted E01](../E01-local-spare-explicit-replacement-v1.0.0/cli-scope-signoff-2026-09-29.md) after the [E05 local repair/reissue prerequisite](../E05-local-repair-reissue-v1.0.0/cli-scope-signoff-2026-09-29.md) was accepted. The only behavioral change from E01 is `StockAllocation.STSIZ=0` for the local repairable LRU. The [contract](contract.json) predeclares a backorder served by repair of the removed item, with exact physical identities and waiting chronology checked in native events. The [parent diff](parent-diff.json) records the two changed tables. The [dated signoff](cli-scope-signoff-2026-09-29.md) records the observed scope and limits.

Run `python build.py` to verify the frozen input. `python build.py --write` creates the input only if absent.
