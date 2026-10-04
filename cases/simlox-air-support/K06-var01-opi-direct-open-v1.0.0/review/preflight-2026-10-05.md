# K06.var01 independent preflight — 2026-10-05

Read-only reviewer verdict: **GO for guarded direct-open diagnostic** on the frozen source bytes. This review preceded the native invocation.

The accepted K02 named input, signoff, closure, native SXI, event log and report matched the contract and runner SHA-256 pins. The SXI was 189,410 bytes. The runner's contract pin matched and PowerShell parsed with zero errors. The installed SIMLOX manual physical page 55 explicitly permits opening `.opi` as a common-format input. Page 110 says a simulation of `model.opi` produces `model.sxo`; pages 167–171 support the JSON export, calculation, report and explicit log paths used here.

The runner copies the accepted SXI byte-for-byte to a new local `model.opi`, then requires session-0 SSH with an `sshd.exe` ancestor, immutable run path, host-wide Issue #18 mutex, protected GUI PID13340/session1 identity, targeted child watchdog, source hashes before/after, and a raw closure. No OPUS10-generated input, two-file merge, `.opo` result point or phase scenario is claimed. The reviewer made no native call or source edit.
