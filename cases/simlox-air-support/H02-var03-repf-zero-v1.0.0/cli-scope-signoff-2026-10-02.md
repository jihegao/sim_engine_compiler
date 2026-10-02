# H02.var03 REPF endpoint native CLI scope sign-off — 2026-10-02

**Decision:** Accept the fixed-seed `REPF=1` repair/restock versus `REPF=0` discard/shortage contrast, subject to independent read-only replay. Publish one bounded H02.var03 slice while Issue #18 remains open.

## Frozen lineage and execution

- Direct accepted H02.var01 source and byte-identical repairable input SHA-256 `82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92`; discard input SHA-256 `bc6f60ec72eebee4621ec742f8684d3371f654ce00d0d75909c3470cf9cfb322`.
- Exact diff SHA-256 `5c393747fce27a4994e61d9efc7a3166788f8f68b74518f060ec0870c89cac38`; pre-run contract SHA-256 `b05af36a42081a94c78d366d918ee9199c2b6996767f4b18b750b2d06ec06579`. Only `DamageItem.REPF` 1-to-0 and description change; 33 tables are unchanged.
- Installed manual physical pp193/426–427 explains default discard for nonrepairable damaged items and REPF override. `TYPE=LRU` and ordinary ItemRepair rows remain unchanged, so their presence alone does not imply repairability after mission damage.
- Both fresh serial runs used the guarded session-0 SSH runner and `Global\SimloxIssue18NativeQueue`. Import, export, calculation, JSON report and authored-table check completed; GUI PID13340/session1 remained preserved at each step. Both arms have exact 24-table authored row roundtrip, converter errors zero, valid logs/reports and 12 sealed raw files each. Warnings #108 and #2053 concern logging and deliberately zero item FRT.

## Native event and report contrast

The repairable arm damages LRU IDs 1/2/3 at h8.78145/20.7434/32.3406, aborts all three launched missions, issues spare IDs 0/1/2, repairs each removed LRU for one hour and returns IDs 1/2/3 to local stock. All three system replacements complete and the aircraft is ready before the next scheduled launch. It ends ready with nominal stock one and no backorder.

The discard arm damages LRU1 at h8.78145, aborts, issues spare LRU0 at h9.28145, discards LRU1 at h9.44811 and becomes ready at h9.78145. It launches at h20, damages LRU2 at h20.1965, aborts, adds a replacement backorder at h20.393, removes and discards LRU2 at h20.5596, and cannot complete fitting without a spare. The h32 mission cancels at h32.3333. There is no item DIRP completion or stock return. The model log records the physical stock issue; report `PNB` is nominal rather than an instantaneous item roster.

Both runs have 72 aligned half-hour System and Stock rows and one ResultSummary row. Repairable/discard counts are `NDAM=3/2`, completed `NREPT=3/1`, `NDD=3/2`, `NWT=3/1`; ordinary failures and lost-aircraft bins are zero. Terminal ready is 1/0, unavailable is 0/1, backorders are 0/1 and nominal stock is 1/0. `MSTF` is 1 versus 2/3 and `MSUF=0` in both, consistent with three versus two aborts plus one cancelled mission. Author replay passed 29/29 checks. The independent replay verdict and all 24 raw seals are bound in `evidence-index.json`.

## Limits

The one-seed endpoint pair tests one directly mounted LRU with one local spare, explicit DamageReplacement and ordinary ItemRepair data. It does not test intermediate REPF probability, multiple damage consequences, other item structures or stations, already-failed items, replacement fallback priority, GUI visual behavior or cross-engine parity.
