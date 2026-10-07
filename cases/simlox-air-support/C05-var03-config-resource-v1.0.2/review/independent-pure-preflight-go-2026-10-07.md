# Independent static preflight: GO_PURE_PREFLIGHT

Decision: **GO_PURE_PREFLIGHT only** for the frozen C05.var03 v1.0.2 bundle. This permits one read-only, actual SSH session-0 PowerShell 5.1 `-PreflightOnly` invocation. It is not approval to start SIMLOX or create either native run.

## Exact frozen identities

- Contract: `b397b217fbf19ec9b6ae9a166a7b3124144f7ec74680675b1fc47b3b69469d0f`.
- Prelaunch manifest: `00a35aa5715856a8819cd5899fb1a1f05ec83fd15539368bbabcca7a539fbd1b`, 27,006 bytes, 77 source records.
- Runner: `65d048f21dfb27982090bba56879a1b77c7c3366a2dd42338275fd34c12a33ca`.
- Behavior validator: `7fb6706ec19de0b9978a91452a22b0a6c7e67eac8ed9742e7afdbbdea4bbf5ad`.
- Report oracle: `4d27180afcb09ac763df3986e5fc215b4954ee9b0a02a7b924453c0a1a841a70`.
- Accepted source verifier: `714d4ab4b734e4503ebbe9f3d5121d4b0f85388c18ed2876deb4f89ec71dcddb`.
- Author self-check: `e2d55d47dad5c7b33a2b6a13217e5f08d03662f9ed32d32a46355bc31476b513` (40/40).
- Reserved, still absent run IDs: `c05-var03-v102-crew-ssh-20261007-01` and `c05-var03-v102-radio-ssh-20261007-01`.

## Independent checks

I rehashed every manifest entry against its exact local byte size and SHA-256 (77/77). The source verifier independently passed 23 accepted local/published Git identities, 48 accepted raw seals, six excluded v1.0.1 preflight/probe pins, all 70 prior manifest entries, installed manual/dictionary, and the installed executable. The frozen v1.0.0 inventories, v1.0.1 draft archives and old no-go evidence remain separate from v1.0.2 source. The v1.0.2 child inputs differ from v1.0.1 only in the versioned description; the child pair retains the frozen 33-table/24-row-containing design, B mission priority 2, and the intended crew-versus-radio resource change. My standard-library `independent_replay.py --self-check` passed the accepted controls and 11 tamper probes; it remains PREP_ONLY and makes no native acceptance claim.

PowerShell parsing reports zero syntax errors. The runner checks actual SSH session 0 and `sshd.exe` ancestry, all pinned source bytes, accepted raw seals, run-path vacancy, the host-wide mutex, and protected GUI PID 13340/session 1/exact start/responding before its preflight branch. The `-PreflightOnly` branch writes a provenance JSON and returns before approval or any run-directory/native step. It starts native work only after a separately sealed `GO_PRELAUNCH` approval and actual preflight JSON are present. Native steps are serial, assert child session 0 after exit, preserve failures, and never stop the protected GUI or a native child. Every `Get-Content` JSON/log read now explicitly specifies UTF-8, addressing the observed v1.0.1 PowerShell 5.1 decode failure; its old runner, failure diagnostic, no-go review, and encoding probe remain pinned.

The validator's live-versus-sealed protocol, physical aircraft and stock event edges, contextual converter warnings, 24-table roundtrip, typed crew/radio behavior, and full 5,210 report-cell gate per arm remain frozen. This review does not predict that the native trace will pass those gates. A fresh independent review of the actual SSH preflight output, GUI/mutex/run vacancy and unchanged source bytes is required before any `GO_PRELAUNCH` approval.
