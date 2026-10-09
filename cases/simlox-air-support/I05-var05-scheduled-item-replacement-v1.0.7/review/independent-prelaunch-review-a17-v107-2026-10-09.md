# Independent prelaunch review A17 — I05.var05 v1.0.7

Decision: **GO_PRELAUNCH**, bound to this exact source freeze, manifest, PowerShell 5 runner, SSH transport and preflight receipt.

The read-only review matched all 113 manifest source roles (bytes, SHA-256 and Windows attributes); preflight receipt source keys/hashes exactly match the manifest. Contract, input, execution contract, parent publication ID/index hash, 12 accepted-parent raw files and SIMLOX executable hash match. The unique run directory is absent; attempt limit is one; `native_dispatch=false`; transport exit was 0 with empty stderr and no retry.

At preflight, PowerShell 5.1.19041.6456 ran in SSH session 0 on 4700-3 with sshd ancestry. GUI PID13340/session1/start1790590196826 was responding and the runner's direct WTS query succeeded (the runner throws unless WTS session 1 is Active). The runner held `Global\SimloxIssue18NativeQueue`, checks no other SIMLOX process or competing runner, and requires the exact absent run path. WTS state is inferred from successful execution of the pinned hard guard; it is not a separate receipt field. Fresh guards and 30-minute receipt freshness are required at dispatch.

This approval covers exactly one v1.0.7 native CLI attempt. It does not accept behavior or authorize a retry. Reviewer made no project, SSH, preflight or native call.
