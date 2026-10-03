# G10.var04 — PASSIVE positive switchover delay

This package is a bounded installed-SIMLOX CLI observation of `TSWOV=0.05` hour in the accepted PASSIVE one-of-two single-item LRU group. Start with the [contract](contract.json), [exact parent diff](exact-diff.json), [native input](native-input.json), [CLI scope signoff](cli-scope-signoff-2026-10-03.md), and [evidence index](evidence-index.json).

The guarded session-0 runner is [run_native_ssh.ps1](run_native_ssh.ps1). Local native artifacts are sealed by the index and closure but ignored by Git under `runs/`. [Author validation](review/author-validation-2026-10-03.json) and a separate [read-only replay](review/independent-readonly-2026-10-03.json) are included.

The first 1-hour candidate is retained locally in `../G10-var04-passive-tswov-v1.0.0/runs/` as an excluded diagnostic: native SIMLOX aborted its pending switch when the first successful mission returned at h10, before the due h10.8829 stop. It is not evidence for a completed 1-hour switch.
