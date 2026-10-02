# H02.var02 two-LRU per-item damage native CLI scope sign-off — 2026-10-02

**Decision:** Accept this bounded two-mounted-LRU `PROB=0.5` deterministic cohort and zero-consequence control. Publish the case while Issue #18 remains open.

## Frozen lineage and native execution

- Behavioral parent: accepted H02.var01 primary-LRU source SHA-256 `82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92`. Accepted G01.var05 quantity-two source SHA-256 `ef21268a1f4c024e0c5bea24136509446e356ea3214dedd694c67825f376f984` supplies a schema/configuration precedent.
- Frozen contract SHA-256 `db6713f6d58677736184483627403793c137ef08fdd8ec8b09ba8e0594a567ef`; exact diff SHA-256 `f3a27b1bbae2e67ae80c698376184a615d3b9700101c82cd4365e4c77c62f581`. The contract binds the nine input SHA-256 hashes, installed executable/manual/dictionary and preselected seeds. Parent-to-control changes only `DamageItem`, `ItemStructure`, `StockAllocation` and description. Child changes are `PROB` and description, plus `RSEED` for seeds2–8.
- Pre-run static review gave conditional GO for nine guarded diagnostic runs. All nine ran serially under session-0 SSH with the host mutex and preserved GUI PID13340/session1. Each completed five steps, 24 authored-table import/export roundtrips, zero converter errors and 12 SHA-256 sealed raw artifacts; total 108 seals. Warnings #108/#2053 are inherited.

## Native observation and limits

The zero-consequence control has three `BATTLE-HIT` events, three successful missions, no damaged physical LRU, spare issue or repair. Across the eight `PROB=0.5` seeds, the three damage events per run yield 4 zero-item, 12 one-item and 8 two-item consequences, totaling 28 distinct damaged physical LRU decisions. Logged physical IDs, stock spare issues, removed-item one-hour direct repairs and returns reconcile one-for-one. Consequential missions abort; zero-item events allow mission success. Two concurrent half-hour replacement tasks occupy one half-hour aircraft repair window. All nine reports contain 72 System and 72 Stock bins, with `NDAM=3` per run, `NREPT/NDD/NWT` equal to damaged-item counts, `NSYRP` equal to affected-mission repair windows, no backorder or attrition, and terminal ready1. Author replay passes 113/113 checks; independent read-only replay passes 598/598 source/provenance plus 33,129/33,129 event/report checks. The [evidence index](evidence-index.json) binds review and local sealed raw files by hash.

Eight selected deterministic seeds show configured per-item consequences; they do not calibrate a 50 percent population frequency or prove independence. This slice has one item type, two identical directly mounted copies, one station and installed engine. Shortages, other structures, GUI visual behavior and cross-engine parity remain unverified.
