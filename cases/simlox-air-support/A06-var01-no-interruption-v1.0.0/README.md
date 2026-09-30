# A06.var01 extendable mission without interruption

This bounded control derives from the accepted [A05 continuous two-aircraft input](../A05-continuous-baseline-v1.0.1/cli-scope-signoff-2026-09-30.md). The [frozen contract](contract.json) changes only `MissionType.MPAT=CONTINUOUS→EXTENDABLE` and a descriptive label. The [builder](build.py) and [exact diff](exact-diff.json) bind the child to parent input SHA-256 `997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea`.

The guarded native run `a06-var01-no-interruption-v100-ssh-20260930-02` starts a two-aircraft mission at hour 8 and completes it successfully at hour 12, with no suspension or failure. Both aircraft return ready. Its event log is byte identical to the accepted continuous control. Its ResultSummary, all 32 SystemResults bins and all 32 StockTotalResults bins match that control exactly; only the report's descriptive label differs. The bins integrate eight aircraft mission-hours, zero suspended, repair and preparation hours, and zero stock demand/backorder. The [author replay](review/author-no-interruption-validation-2026-09-30.json) passes 157 checks.

An initial guarded run `a06-var01-no-interruption-v100-ssh-20260930-01` completed the native CLI but its copied roundtrip checker assumed 16 populated source tables. This source has 13. The checker was corrected and the final run used a new immutable directory. Both raw runs remain under ignored `runs/`; the accepted run and source hashes are in the sign-off.

This one no-failure configuration establishes the catalog's no-interruption boundary only. Finite suspensions, report-window crossing and an unfinished horizon have separate evidence. GUI visual behavior and cross-engine equivalence remain unverified.
