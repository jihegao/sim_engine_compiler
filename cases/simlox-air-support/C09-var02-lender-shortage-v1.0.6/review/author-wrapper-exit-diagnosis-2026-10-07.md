# C09.var02 v1.0.6 wrapper exit diagnosis

Decision: **NO_GO for the v1.0.6 child.** This is a read-only diagnosis of the one sealed run `c09-var02-v106-shortage-ssh-20261007-01`, not a repair or a native rerun. The prospective lender-shortage behavior was not calculated or reported.

## Sealed boundary

The frozen manifest has 809 source records and SHA `c947689e327a60cbd4a0e805978d5b13d050a612d065ac5ece6ab5481fe5e6c8`. The sole run's closure is 211,638 bytes, SHA `3715388705404b8a78f92b9201433ebd1b4660a8c9628a5e2d39e45b6367924f`; failure seal 2,939 bytes, SHA `584e65809959f086a30c6d67f3797e9009d861253ffcd9d178fe3714d64dde99`. I independently rehashed 8/8 closure raw records and 10/10 failure-seal file records, with zero mismatch. The closure's before/after source maps are equal. Root's separate read-only freeze proof is `tmp/c09-var02-v106-failed-run-freeze-20261007.json`, SHA `e0d3825b3fb62e6995377a263aa6fad20d86c929e6990db5776c0998c85122c5`.

The import and export stages each recorded child session 0 and exit code 0. `roundtrip-validation.json` is 313 bytes, SHA `fcdfde44773a829b3bf14d7f58d73685fadb9ee76d2e68195ec261164d7c228f`; it reports `passed: true`, 25 row-containing authored tables and no issues. Its export SHA matches the sealed `roundtrip-raw.json` SHA `f1988afef7211b87da004f67826fce4614bd6b9510ac87ab846ad3973f5ac25e`. The check's stderr file is empty. `steps.json` (SHA `03a971e3cebc6bd4b61a5a3c8be78c6a8cb4b8f7a210b0132fd7ea897872e530`) records `check_import_export` PID 10552 in session 0 with `exit_code: null`, status `failed`. No calc, converter summary, SXO, model log or report stage exists. The passed checker output does **not** prove the child's operating-system exit code.

## Exact wrapper cause

The frozen `run_native_ssh.ps1` is 16,026 bytes, SHA `9a79d09848d5bd54a00fe0199f7b2389e42fd2e2b188e6995260983b895f9a1d`. In `Check-Step`, it starts the Python checker with `Start-Process -PassThru -RedirectStandardOutput ... -RedirectStandardError ...`, calls `$check.WaitForExit()`, then reads `$check.ExitCode`. Under the installed local Windows PowerShell 5, I reproduced this **same process-launch pattern** using harmless bundled Python scripts that exit 0 and 7: both reported `HasExited=True` but `$p.ExitCode=$null`. Adding `-Wait` to `Start-Process` while retaining `-PassThru` and both redirects reported exit 0 and 7 respectively. `Refresh()` after the manual `WaitForExit()` also left the 0-case exit code null in a separate harmless control. All probes used temporary files outside the repository, cleaned afterward; none invoked SIMLOX or touched run evidence.

The wrapper's `$step.exit_code -ne 0` is true when `exit_code` is null, so it rejected the checker despite its passed JSON. The original exit status remains unobserved; the local probe identifies the wrapper mechanism, not a retrospective proof that PID 10552 exited 0.

## Recovery boundary

Preserve v1.0.6 source, approval, receipt, closure and failure seal byte-for-byte as excluded. A separately versioned child with a unique run ID may keep the same one-cell source hypothesis and replace only the checker process-wait/exit-capture implementation. Before any fresh native approval, the new production wait function should be exercised under actual SSH PowerShell 5 file invocation with harmless Python exit 0 and 7, required non-null integer exit codes, captured stdout/stderr, and rejection of null or nonzero. It then needs a new frozen manifest, independent static review, actual `-PreflightOnly` receipt, and distinct `GO_PRELAUNCH`. No v1.0.6 retry or inherited approval is valid.
