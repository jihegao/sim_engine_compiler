# D16.var03 PM-specific remote route

This bounded fixed-seed pair tests a CAL24-specific `PMStationStructure` link against the generic `StationStructure` link in the accepted D12.var04 remote PM model. The [contract](contract.json) freezes both inputs and its acceptance gate. The [signoff](cli-scope-signoff-2026-10-05.md) describes the observed route, report reconciliation and limits.

The guarded [native run](run_native_ssh.ps1) completed 8/8 steps, retained 22 SHA-sealed local raw files and preserved GUI PID 13340. [Author replay](review/author-validation-2026-10-05.json) passed 109/109; [independent replay](review/independent-verdict.json) passed 627/627 with a bounded GO. The [evidence index](evidence-index.json) records source and local raw hashes; `runs/` remains ignored by Git.

The [v1.0.0 diagnostic](../D16-var03-pm-specific-route-v1.0.0/README.md) showed the physical route contrast but failed its frozen exact-roundtrip gate, so it is excluded from publication.
