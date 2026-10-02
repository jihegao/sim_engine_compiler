# I01.var03 bounded CLI signoff — category-aware task binding

Status: accepted for the precise four-arm category/APID scope below, subject to exact-head PR CI and merge. Issue #18 remains open.

## Frozen source and experiment

- Direct accepted parent: I01.var03 maintenance station base input SHA-256 `4e16325638ff7aafcf47306101b42a780c02b06f957c0036317e300eb63abf72`, merged in PR #254 before these native runs. Its own accepted parent is I01.var01 stocked and its station structure comes from accepted E04 FAST.
- Four frozen input SHA-256 hashes: basic-real `814db560714d31e71a749bed0aabfb6f8c539dbca96faca02df1c15c95c38b52`; depot-real `60842193df76839810edd32f4b58f7aac0beca6f4f4ad49a4cebf1397dc3a615`; basic-alternate `a5e29e24614647ab8f7ffdd523b331466d21d21c8c42e89f469d5624e227f652`; depot-alternate `d402b6f7453ec9426f6504a3dec38322743be825e889d0577ee6af5b035c9683`. Exact diff SHA-256 `fd4f1afdb5253cdcd74527d69cb28bf1cd19331a7bf2b58ff7e2917b461b0d1f`; pre-run contract SHA-256 `c2ca3160f501b131b15ed447125a0637bada8973df32bf7c238e7219b8246c57`.
- ItemRepair at BASE and DEPOT always references fixed task ID `I01-LRU-DIRP`. The two Tasks rows have equal neutral descriptions and TLID BASE. Across source layers, only their TCID cells swap (`LRU-CM` ↔ `DECOY-CM`) plus description. Within each layer, only `Control.APID` and description change. Both APIDs allocate both categories at crossed stations, while BASE spare1/DEPOT spare0 and one-hour repair rows remain fixed. No ItemReorder or ResourceAllocation business rows are authored.
- Installed manual physical pp. 338–339 and 439–441 defines referenced task category/level and station matching. Installed SIMLOX executable, manual and table dictionary hashes are pinned in the contract.

## Native and independent evidence

- Four fresh, serial, guarded session-0 SSH runs used `Global\SimloxIssue18NativeQueue` and preserved GUI PID13340. Each source-stable closure has no error; all 24 row-containing authored tables round-trip exactly, converter errors are zero (warning #108/notice #2034 only), SXO/report output is valid, and 12 raw files are SHA-256 sealed. Total local raw seals: 48; bulky raw artifacts are ignored by Git.
- Every arm has physical LRU ID1 failure h9.8829, spare ID0 draw h10, aircraft ready h10.5, two later mission successes and terminal ready1. The repair route crosses BASE/DEPOT/DEPOT/BASE in the order basic-real, depot-real, basic-alternate, depot-alternate. BASE repairs ID1 h10.1667–11.1667 and restocks immediately. DEPOT receives ID1 after two-hour outward transport, repairs h12.1667–13.1667, returns it over two hours and restores BASE stock1 h15.1667. The depot arms show a temporary backorder. All 72 SystemResults and StockTotalResults bins and business summaries reconcile across all four arms and to the accepted station parent; raw physical logs prove route and stock timing.
- Author replay: 45/45 checks, SHA-256 `a282e62300372132b3cacd5484c26bba44d5450f634d7c8527ae141b14c05a3e`. Separate read-only replay: 1,742/1,742 checks, checker SHA-256 `8ae8d13817d3e9d12229507910e721c20c241ddad626427926094d3983dd73c3`, verdict SHA-256 `b8074a3aad195e3f4bdb6c52aa64809265e6782eaf2b41bc0bcbe435cda9fda7`.

## Scope and limits

This accepts category-aware binding of one task-referenced LRU repair in interaction with APID selection. The second task is inert; no competing live repair demand is tested. Station transport and stock timing are coupled downstream effects. Task-level filtering, simultaneous three-allocation POINT selection, `<NONE>` reorder, generic station routing, GUI visual behavior and cross-engine parity remain unverified.
