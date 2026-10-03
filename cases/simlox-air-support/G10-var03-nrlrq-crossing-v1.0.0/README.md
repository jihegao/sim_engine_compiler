# G10.var03 — ACTIVE 1-of-2 NRLRQ crossing

This bounded installed-SIMLOX CLI candidate derives from accepted [G10.var01](../G10-var01-active-single-link-v1.0.0/cli-scope-signoff-2026-10-03.md). The [contract](contract.json) predeclares a fixed-seed two-link failure crossing; [input](native-input.json) and [exact diff](exact-diff.json) freeze the matched System/Item FRT panel.

The [guarded runner](run_native_ssh.ps1) uses session-0 SSH, a host-wide mutex and preserved GUI PID13340. Raw native input, SXI/SXO, logs, report, invocation and closure remain in ignored `runs/` and are sealed in the [evidence index](evidence-index.json). The [author validation](review/author-validation-2026-10-03.json) and separate [independent replay](review/independent-readonly-2026-10-03.json) check events, stock/repair ledgers and all 72 report bins. See the [CLI scope signoff](cli-scope-signoff-2026-10-03.md) for observed behavior and limits.
