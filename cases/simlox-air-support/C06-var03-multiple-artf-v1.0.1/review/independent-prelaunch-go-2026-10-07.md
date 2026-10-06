# C06.var03 v1.0.1 independent exact-file prelaunch review

**Decision: GO_PRELAUNCH for one protected two-arm native invocation.** This is a source, runner, and guard approval only. No v1.0.1 native child exists and no behavior has been accepted yet.

## Frozen identities

- Contract SHA256 `48a29f63e819e85dc3f9de856199c63441f32f34104dade338ef1ca246bd2384`; v1.0.0's contradictory contract remains excluded with its `NO_GO_CONTRACT` memo intact.
- Manifest SHA256 `96e62ff1d1bd532df45bca301b5d3635fad9a636d8a6de0c91b7dd01d58648e7`; all 31 source entries matched both byte count and SHA256 on disk. Its runner, validator, factor1 input, and factor3 input pins are respectively `741c0af998ccf3a5e81933fbabae2ed1c9c77a09fc53b2137cbd244065e274c2`, `d51e2d62a45e2c136a0c4b119270d2c80560bb6eb26d2fd108581cde144a20c6`, `c9da3e83e4b270ab93c02c167932f86cfee2096a8aeb5947de7bad7a77cc2231`, and `074c9e098edc0e81746dfb9978c6610b1be17a967bbbbc5c4f8949bd5a0bb1d3`.
- Accepted C06 and C03 published/local source identities, immutable closures, and 12+11 raw seals passed 270 independent source/raw/delta checks with no failure. Both child inputs are exact parent additions: common Resource and ResourceAllocation rows, one additional SubTaskResource row with ARTF 1 or 3, and corresponding description. The pair differs only in description and second ARTF.
- PowerShell parser returned zero syntax errors. Static negative probes rejected a changed authored row, column, instance name, source byte, mission time, and report cell. Independent event-ledger synthesis passed all 5,442 report checks per arm; an injected SystemResults cell error was detected exactly. These are static tests, not native evidence.

## Protected execution gate

The **clean** actual loopback SSH command used `ssh -n ... powershell.exe -NoProfile -NonInteractive -File run_native_ssh.ps1 -PreflightOnly` and exited zero in 2.09 seconds. Its JSON at `review/preflight-ssh0-20261006T231153895Z.json` has SHA256 `9f4aab50e7babeeaf56d6c504968d5bc026a3abb9bd921e51b05923e802fdf63`. It records SSH session 0 with `sshd.exe` ancestry, free `Global\SimloxIssue18NativeQueue`, protected sole GUI PID 13340/session 1/start 1790590196826/responding, both reserved run directories absent, 12+11 accepted raw seals, all 31 manifest hashes, and `native_process_started=false`.

The earlier invocation without `ssh -n` wrote a byte-identical preflight JSON and released its mutex, but its SSH transport stayed open. The controller closed only that SSH client after confirming no native process and the GUI intact. The approved invocation must use `ssh -n`; this approval binds the clean preflight path above.

The final runner checks source hashes, unique run paths, SSH0/sshd, mutex and GUI identity before native calls. It executes serial import, export, exact roundtrip, calc, default JSON report, and behavior check for each arm; preserves steps and raw SHA/size closure on failure; and no longer contains a `Stop-Process` watchdog. The author behavior gate demands zero errors, only #108/#126 warnings, typed per-aircraft alternative selection, max-factor timing, and complete six-table reports. The independent postrun replay remains pending and is required for bounded acceptance.

**Limit:** This prelaunch GO authorizes only the two frozen run IDs in the approval JSON. It says nothing about whether native SIMLOX will satisfy the factor or report hypotheses.
