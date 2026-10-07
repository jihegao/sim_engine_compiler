# Independent exact-file static gate: GO_PURE_PREFLIGHT

Decision: **GO_PURE_PREFLIGHT** for the single read-only SSH0 / Windows PowerShell 5 `run_native_ssh.ps1 -PreflightOnly` invocation. This decision does not approve a native child. A separate review of the actual SSH receipt and a fresh exact-file `GO_PRELAUNCH` are required before the unique v1.0.6 run may start.

## Frozen identities

- Contract `17786d6f6aec8124f76b97eff58f38c3382bd301b3647acb95acf3ba199eeec8`; child input `a036c16bbdd28b35047ba8a064722c6a1bde21c036435263dd5713dd710767a4`.
- Prelaunch manifest `c947689e327a60cbd4a0e805978d5b13d050a612d065ac5ece6ab5481fe5e6c8`, 281,754 bytes, 809 unique source records. I independently read and rehashed all 809 current files: zero SHA or size mismatches. The reserved `c09-var02-v106-shortage-ssh-20261007-01` directory was absent.
- Runner `9a79d09848d5bd54a00fe0199f7b2389e42fd2e2b188e6995260983b895f9a1d`; behavior validator `2ddb737a6d9aacb396657c37623c57d0ea826bd3e740dca7463fcc4c73a7cf29`; source verifier `0316128c369022475115cb51a01d4def2ab8a41966be5b3d8bdb38a7b0bc58ce`; physical ledger `039ae3872cb85be34ba59b1e1f6c2b2df9ba8414de179c0d5c8423d0b48d4229`; report oracle `c4435a5267ed5a07f03337b40dd9b3ab483e8bc0f0a25e591497bd67e59511b4`.
- Production receipt gate `2c1e3333b8092960f399c88f167a8f481a5d9489cadd365dff09d06e770e0400`; same-function test `36f1c7de83844175c20c7646bb439c261c6199daa0b4a9ee7aae453a30d4f0b4`. Installed executable, dictionary, manual SHA pins in the manifest matched `fe24c5bf…`, `11a61537…`, `39427027…` respectively.

## Independent static checks

- The read-only source verifier passed 64 contract literals, 101 accepted local/Git source pairs, 77 distinct dual identities, 130 raw seals, ten closure/invocation chains and both excluded attribute files. The v1.0.5 frozen 384-record manifest is checked separately; current shared catalog bytes are required before a live run, with exact owned historical archive and base Git identities for later sealed replay.
- A dry manifest rebuild reproduced the same SHA and 809 records. The frozen input and exact diff have two intended cell changes only: `ResourceRemoteSupport.TTRSS` 0.5→0.125 and `ProblemDescription.PDESC`; all other 32-table source cells and metadata remain matched to the sealed ordinary control.
- The author static self-check passed four separate 1,754-cell paths: accepted ordinary control, synthetic shortened return, one later linked repair, and two sequential repairs within one later loan. Thirty semantic mutations rejected, including wrong task booking, balanced orphan mechanic allocation/deallocation, shifted typed receipt and changed source-exact/nullable report cells. A last-bin resource mean may remain fractional even when the h12 event state is closed. These synthetic fixtures are code coverage, not native evidence or fixed-seed predictions.
- I parsed all nine Python source files without code execution and all three PowerShell files with Windows PowerShell 5 AST: zero syntax errors. I separately ran the production receipt function test under local PowerShell 5: two positives and 33 rejections. Direct string-typed JSON guard probes that were accepted in the mutable draft now reject; the frozen function rejects reparse points along the owned receipt path.
- The runner has a unique-path check, live SHA/size checks, SSH0/`sshd.exe` and protected GUI identity guards, a host-wide mutex, hidden serial child processes with session-0 and exit checks, UTF-8 JSON reads, six ordered steps, source-before/after checks, and closure/failure seals. It neither kills a child nor invokes native code in `-PreflightOnly` mode. The original v1.0.2 ordinary failure and unstarted shortage arm remain excluded; this gate does not promote either old prospective pair.

## Scope of this GO

The actual SSH5 file invocation has not yet been observed. It must return exit 0 with a byte-sealed receipt showing SSH0/sshd ancestry, free mutex, GUI PID 13340/session 1/start 1790590196826 responding, all 809 source pins and accepted raw seals, absent child run, and `native_process_started=false`. The reviewer-owned `independent_replay.py` is intentionally outside the manifest and remains mutable; final native approval must bind its then-frozen SHA and the exact SSH receipt. No native launch is authorized by this memo.
