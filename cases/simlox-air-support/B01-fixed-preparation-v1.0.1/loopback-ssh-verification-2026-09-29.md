# B01 1.0.1 permanent loopback SSH verification — 2026-09-29

This supplements the [accepted B01 1.0.1 evidence](evidence-2026-09-29.md)
after PR #48 was merged at `44ca49d6cc15e528a0845c670ae3f18acff1c429`.
It changes no model, contract, validator or acceptance decision. The verified
local RSA key fingerprint was
`SHA256:fuJqCedomdwtp4SRRoGMT5KEnEqym3+MmRQxNdvo9lo`; no private key bytes
were copied or recorded.

The exact session-zero probe in
`C:\Users\user\Downloads\simlox-loopback-ssh-20260929.txt` returned `0`.
The exact direct SSH `powershell.exe -File run_native_ssh.ps1` command was
then attempted with fresh ID `b01-v101-ssh-20260929-07`. Its SSH PowerShell
child stalled before the runner's first message; no run directory or SIMLOX
CLI child appeared. Only that verified stalled PowerShell child was stopped.
The existing GUI PID 13340 remained responsive. ID `-07` is not evidence.

A short PowerShell wrapper invoked the unchanged B01 runner through the same
authenticated RSA loopback SSH route with fresh ID
`b01-v101-ssh-20260929-08`. It printed `session=0; SSH=True`, then the runner
verified `SSH_CONNECTION`, `sshd.exe` ancestry, source and A01 hashes, the
native queue mutex, and original GUI PID 13340. The GUI was responding in
session 1 before and after execution; it was never closed or restarted. All
four native CLI steps exited 0. The runner's validation and the separate
[independent read-only replay](review/independent-readonly-loopback-2026-09-29.json)
both returned `passed=true` and zero differences. The independent replay found
11 closed raw files, 12 matching business tables, 72 half-hour result
intervals, `NPSTA=NPSUC=1`, `NSYMP=0.5` and `FTMO=NSYMO=2`.

Raw directory on host 4700-3:

`C:\Users\user\dev\sim_engine_compiler-b01-v101\cases\simlox-air-support\B01-fixed-preparation-v1.0.1\runs\b01-v101-ssh-20260929-08`

| File | SHA-256 |
| --- | --- |
| B01 native input | `2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b` |
| Exact A01 parent diff | `79c801e621e6872b823e9558d3b9bdb2fe0555acdce34bb33147698695c9bb92` |
| `invocation.json` | `1f9b64de4c46bc961c227432f4e92423734c4b251178796a514a0632c8494630` |
| `closure.json` | `e8294019b985690f9e2081e4f4520d8558a612794eb9f957273cb67e35ecff53` |
| `run-manifest.json` | `357231e209a35b81e8d99308147e5492b6f8035b7aad6184d154c861454f24bd` |
| `validation.json` | `d21c8d80d4ed0c7eae564a0f957a90969ac587a04630846d7442ba2cf76a9aff` |
| `model.sxi` | `3681e0a3daf17ce47d79f4bf8460c52c69d1b09ae63c78dc8491f14c4d888524` |
| `model.sxo` | `9531ee98c1adcbf24fd0cdc6518da186bb6200be0430863a913c8bd443fdf103` |
| `model.log` | `140dab2eb1031c8b6e6cff68f82b6d8004236ec71029d27d92daa1334250ad5f` |
| `report-raw.json` | `6e552899a0ef726891e4fabb03effc5cd25e9bc7fc38756da02bf231e1389f23` |
| Saved independent review | `8006d17765aa577675db4f9113f14a005b5f1bbe2569fa993cd8ea1697f0e92d` |

`build.py --check`, 18 related local unittests, PowerShell parsing and Git
whitespace checks passed before this rerun. GitHub Actions zero-step failures
remain billing/quota failures, not test passes. The bounded B01 1.0.1
acceptance from PR #48 stands; GUI-only behavior, internal object creation
counts and a causal launch delay remain outside that claim. No B02 work was
started.
