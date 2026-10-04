# I03.var01 independent preflight — 2026-10-05

Read-only reviewer verdict: **GO for guarded native diagnostic**, with exact authored-table roundtrip and behavioral gates retained. The review preceded the native invocation.

The reviewer matched the on-disk contract, builder, runner, and all three input hashes to their frozen pins; the PowerShell runner had zero parse errors. C03 staffing-2, its accepted evidence, C08 input/signoff, and installed manual/dictionary matched their expected SHA-256 values. The two `OperationProfile` records share PRID/SPRID but differ at STIM 8 versus 20, the third key. `ResourceTransfer` uses the installed seven-column, four-key schema. Its OUT/IN polarity, delayed busy-resource OUT, and IN transfer delay follow manual physical pages 225–226 and 478–479.

The parent-to-control delta is one second scheduled formation, a seven-cell all-null transfer placeholder, and description. Control-to-out replaces the placeholder with OUT at h7.75; out-to-out_in adds IN at h10 with TFDT0.5. All other model tables remain identical across arms. C03 shows both crew busy from h7.5 to h8, so the OUT request should wait. The control placeholder was an explicit, unverified roundtrip risk. A native result was **not** inferred at preflight.

The runner requires session-0 SSH and an `sshd.exe` ancestor, an immutable run ID, the host-wide mutex, protected GUI PID13340/session1 identity, a targeted native-child watchdog, source hashes before/after, and a raw SHA-256 closure. It schedules 12 serial import/export/calc/report steps.
