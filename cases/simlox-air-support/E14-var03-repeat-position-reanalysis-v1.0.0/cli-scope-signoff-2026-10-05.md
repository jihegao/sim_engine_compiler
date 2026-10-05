# E14.var03 repeated SRU position: bounded CLI evidence mapping

**Decision: ACCEPT a bounded read-only E14.var03 mapping of already accepted native behavior.** This package does not contain a new SIMLOX run or a new controlled model change. It identifies the catalog's repeated-same-position boundary in the accepted E14.var01/02 joint `RRF=4,NFFF=2` five-seed panel and makes the witness independently replayable. E05 is the accepted instructional prerequisite.

The [contract](contract.json), SHA-256 `98276fcfc76d61bd6ee781fea1b54d889d0043150219de0b77830566e6223f8e`, pins E05 signoff and accepted E14 parent signoff, both native and selected-report closure hashes, parent independent verdict, and two distinct evidence-index byte identities. The historical local index is 33,683 CRLF bytes, SHA-256 `7f2318d933bc0281aac2b70c82d65fae0b97c6b4c08d5a7cb8b0cb6913f7d684`. The published `simlox/main` Git blob at commit `94a6dcdf6d175e98a00ffdf9c0fdc2a0102cd962` is 32,883 LF bytes, SHA-256 `9e12915cdc2679f04d84cab7113311b761396df5f86e937b3ea6f84037272942`. CRLF-to-LF conversion produces those exact published bytes; parsed JSON also agrees. Neither byte identity is substituted for the other.

The accepted parent native closure is `a89e5ef615ff2fb9f3eb5205e9d6e8b45a8770c755f42aec9d68a6155aef6bdb`; its selected-report closure is `529218c7539914e3df5d3a1f3bd53f9abeba7db2b9f2a39def11e66287fa4f16`. Both replays verified all 164 local parent raw SHA-256/size seals. The independent replay also checked all 23 parent source records against checkout and published Git blobs. The accepted native run originally used SSH session 0, the host-wide mutex and protected GUI PID 13340/session 1. No native child or GUI capture was started for this derived mapping.

| Extra-arm seed | Total extra removals | Same-task/LRU/SRU repeated groups | Events in repeated groups |
| --- | ---: | ---: | ---: |
| 2 | 5 | 2 | 5 |
| 3 | 1 | 0 | 0 |
| 4 | 2 | 1 | 2 |
| 5 | 7 | 3 | 6 |
| 6 | 0 | 0 | 0 |

The six groups contain **13 of the 15** observed extra removals; all five paired controls have zero. Seed 2 includes a three-removal `TEACH-SRU-02` group on one physical LRU. For every repeated event, the raw log binds the same SURP task, LRU physical ID and SRU IID; removal times increase, the prior fit subtask finishes before the next removal, removed physical IDs differ, and each removal creates its own demand and distinct physical stock issue. All 20 paired SRU selected reports have the expected IID/BASE-01 selector and 72 contiguous half-hour `ItemResults` bins. Full parent stock occupancy and item ledgers remain covered by the accepted parent independent 3,514/3,514 replay.

The [author focused checker](validate.py), SHA-256 `0ce2f5ef6073bd40f36b2ec738d9f844a3b494773ac85278807165939608ccce`, passed **412/412** checks with [verdict](review/author-verdict.json), SHA-256 `6c1bc78f10485a5cdb5be5f3486c3531f2c489b07ce80553dd331bfac0882030`. A separately authored [read-only replay](review/independent_replay.py), SHA-256 `19e3146926c119dcb5f803177335059465f119e7d3ce6f5e2a6d58735d395f19`, passed **300/300** checks with [independent verdict](review/independent-verdict.json), SHA-256 `56ccc1aa83bc865c6758889ea3a4a02ce12ecd60e315eb8bef84375b05ebc11c`. The independent replay additionally checks fit completion, report selector identity and contiguous time grids.

The separate E14.var04 `NFFF=0` [failure diagnostic](../E14-var04-nfff-zero-v1.0.1/failure-diagnostic-2026-10-05.md) remains excluded: its v1.0.0 preflight stopped before native execution; its v1.0.1 native import erased the zero cell and exact roundtrip stopped before conversion. It is not evidence for a converter boundary or E14.var04 acceptance.

**Limits:** The repeat witness reuses one accepted joint-parameter panel, with no independently varied repeat parameter. It does not estimate repeat frequency, isolate `RRF` from `NFFF`, assert that every seed repeats, generalize to other item structures, verify GUI-only behavior or cross-engine equivalence, or close E14 or Issue #18. K01/K08 GUI observations remain blocked without capture retries.
