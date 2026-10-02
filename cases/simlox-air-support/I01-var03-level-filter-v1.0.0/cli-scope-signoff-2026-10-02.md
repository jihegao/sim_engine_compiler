# I01.var03 bounded CLI signoff — level-aware task binding

Status: accepted for the precise four-arm level/APID scope below, subject to exact-head PR CI and merge. Issue #18 remains open.

## Frozen source and experiment

- Direct accepted parent: I01.var03 maintenance station base input SHA-256 `4e16325638ff7aafcf47306101b42a780c02b06f957c0036317e300eb63abf72`, merged in PR #254. Its station structure derives from accepted E04 FAST.
- Four frozen input SHA-256 hashes: basic-base `483a99ec2c4512f2b02c7f67f08e76b7ac218470ba64b0ecadc91c1db4a9daae`; depot-base `7bfaf8c27031ecf2b3d40b6f0ac205e73f05d2a0596de0e98003d2ba0d8e1a14`; basic-alternate `db3bc659639c47111b3b0c194013b98f43cad98ba949b222ce2afd5bad6ecc81`; depot-alternate `4b5903ef79ff983a8c0850af02acec945e6a091f138a28e68976639e6396eb79`. Exact diff SHA-256 `9762c558f4f3d1dc3a35ab2c4a3a41c55c262ef34f2c160fa6320021e8823d0a`; pre-run contract SHA-256 `84e3fc4b7ec599eceac5073b6b28f596e957cdeae0035f9f33c3471a1a66bd16`.
- ItemRepair at BASE and DEPOT always references fixed task ID `I01-LRU-DIRP`. The two Tasks rows have equal neutral descriptions and TCID `LRU-CM`. Across source layers, only their TLID cells swap `BASE` ↔ `ALT` plus description. These map to TaskLevel LEVL1 and LEVL2. Within each layer, only `Control.APID` and description change. Both APIDs allocate both levels at crossed stations, while BASE spare1/DEPOT spare0 and one-hour repairs remain fixed. No ItemReorder or ResourceAllocation business rows are authored.
- Installed manual physical pp. 338–339 and 439–441 describes referenced task category/level and station matching. Installed SIMLOX executable, manual and table dictionary hashes are pinned in the contract.

## Native and independent evidence

- Four fresh, serial, guarded session-0 SSH runs used `Global\SimloxIssue18NativeQueue` and preserved GUI PID13340. Each source-stable closure has no error; all 24 row-containing authored tables round-trip exactly, converter errors are zero (warning #108/notice #2034 only), SXO/report output is valid, and 12 raw files are SHA-256 sealed. Total local raw seals: 48; bulky raw artifacts are ignored by Git.
- Every arm has physical LRU ID1 failure h9.8829, spare ID0 draw h10, aircraft ready h10.5, two later mission successes and terminal ready1. The repair route crosses BASE/DEPOT/DEPOT/BASE in the order basic-base, depot-base, basic-alternate, depot-alternate. BASE repairs ID1 h10.1667–11.1667 and restocks immediately. DEPOT receives ID1 after two-hour outward transport, repairs h12.1667–13.1667, returns it over two hours and restores BASE stock1 h15.1667. The depot arms show a temporary backorder. All 72 SystemResults and StockTotalResults bins and business summaries reconcile across all four arms and to the corresponding accepted station parent route; raw physical logs prove route and stock timing.
- Author replay: 45/45 checks, SHA-256 `aceb85d4e290d1249f866f428c67cfaab76408871a40e91b8d5dc5462bcdbed4`. Separate read-only replay: 1,754/1,754 checks, checker SHA-256 `559e45e1da313fe2f78ce0ea754f533e4876968413608930d9578934529b79d8`, verdict SHA-256 `4760a11bcdd8849681bc508513c9722d4413db007ccd7a794f82fc13b817f620`.

## Scope and limits

This accepts level-aware binding of one task-referenced LRU repair in interaction with APID selection. TLID label and linked numeric LEVL mapping change together, so their separate effects are not established. The second task is inert; no competing live repair demand is tested. Station transport and stock timing are coupled downstream effects. Category interaction, simultaneous three-allocation POINT selection, `<NONE>` reorder, generic station routing, GUI visual behavior and cross-engine parity remain unverified.
