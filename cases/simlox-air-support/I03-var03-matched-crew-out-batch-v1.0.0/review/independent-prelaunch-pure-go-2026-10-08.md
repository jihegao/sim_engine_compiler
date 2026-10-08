# Independent control pure preflight gate — GO_PURE_PREFLIGHT

**Decision:** GO_PURE_PREFLIGHT for exactly one root-owned, zero-native SSH session-0 Windows PowerShell 5 `-File run_native_ssh.ps1 -Arm control_out1 -PreflightOnly` invocation through the pinned neutral transport. This decision does not authorize `native` mode, the child arm, a retry, or publication. A fresh actual preflight receipt, source-map review, and separate GO_PRELAUNCH remain required before a native child.

## Exact frozen identities

- Case: `I03-var03-matched-crew-out-batch-v1.0.0`; reserved control run `i03-var03-control-out1-v100-ssh-20261008-01` is absent.
- Frozen v6 contract: SHA-256 `17ab577282e2186040d93195500e9df7565db51922b75468ffe62cc60c7fb30d`.
- Source inventory: 25,519 bytes, SHA-256 `68213e358cda15de0874b48b0cc03f1c4bfe09b2896f69d8fb4a07b7bf9a158f`; all 135 owned source records exact.
- Control prelaunch manifest: 144,254 bytes, SHA-256 `d5dad85a3f2b9f3aeba1c2f6e463a1fd7d504a7481d8c0ecfc8c0ac9a4e8fb06`; all 349 source records exact; independent source-map SHA-256 `06fd01582131c6a74037905d6b90f0c91e06fc57cf968b5dad399baa2ee86428`.
- Runner `run_native_ssh.ps1`: 22,601 bytes, SHA-256 `c826a3e989d961fd788e851c55f40f2ec610255ef3e2dac53540a0e860938118`; neutral `ssh_transport.py`: 4,232 bytes, SHA-256 `1e766cf59f4fc5118abcc3f6c645fda39c70c38bb5f39e004325d3d6761ec9b8`; production preflight receipt parser: 5,919 bytes, SHA-256 `fcfedf04e36996cef2ca4c009ded07b8a7903e2f26ffbdaf094c930d2a98a320`.
- Independent replay: 63,558 bytes, SHA-256 `c45bcc2c696031ce04a687086fa266aa01446a2504a02f93aa053d8163ede037`; self-check: SHA-256 `6fc11bbcb837344aeb9423ee28f0c42004a239ae6e557fc3fd3b46bb1fbb5075`.
- Author handoff: SHA-256 `797dd4ba25608553b837f55f129cb3cffd08d086e44d0ba80a476b3aae41fb31`; root one-time source-freeze receipt: SHA-256 `9909f51ba6a0eb9fe9361d9f09cbe79036461c2fd2d15a508ea678c6a699cb45`.

## Independent checks

The read-only auditor `tmp/i03-var03-independent-control-source-audit-20261008.py` (SHA-256 `65bba60f5fc22f4e73b9944d917dfe9c84eafd6ba34e3e62d1a6f021976e5262`) passed and emitted `tmp/i03-var03-independent-control-source-audit-20261008.json` (SHA-256 `e557114f0c1a60d2c904be4d222a755854ffd7e2e29e8313c38b949449c02ddc`). It rehashed all 135 owned sources and all 349 manifest records; invoked the frozen independent source/manifest gates; checked 17 accepted parent and 63 prerequisite disk/Git identities, 34 + 78 mandatory original raw records, eight docs, three installed pins, and exact owned catalog archive plus typed live 493-entry prefix and unique publication IDs. It verified the control manifest has `prior_control: null`, no sealed control files, and no reserved run, preflight receipt, or approval.

The root source freeze captured the actual binary stdout/stderr and integer-zero exits of its one-time inventory/manifest writes; both stderr streams were empty and no native run was started. The prior independent PURE proof independently exercised both synthetic arm traces, each 5,210-cell predicted report, source controls, and semantic negatives; these PURE fixtures are predictions and supply no native acceptance.

The frozen runner serializes six stages under the host-wide mutex, binds source hashes, checks exact GUI PID/session/start and WTS, requires an absent selected run, and in `-PreflightOnly` returns before creating the run or invoking SIMLOX. The neutral transport makes one fixed SSH `-File` call, captures original byte streams, and has no post-connection timeout, kill, or retry. Actual SSH0/PS5 ancestry, live GUI/mutex state, and source-map values must be established by the new receipt and independently reviewed before any GO_PRELAUNCH.
