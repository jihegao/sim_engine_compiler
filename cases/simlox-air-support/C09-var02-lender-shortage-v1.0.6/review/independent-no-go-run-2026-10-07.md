# Independent v106 run diagnosis — NO_GO_RUN

The single approved child `c09-var02-v106-shortage-ssh-20261007-01` is **NO_GO_RUN**. It stopped at `check_import_export` before calculation, converter diagnostics, model events, or report export. It provides no evidence for the planned TTRSS shortage outcome. The accepted ordinary control was not rerun.

## Exact sealed evidence

- Frozen contract SHA `17786d6f6aec8124f76b97eff58f38c3382bd301b3647acb95acf3ba199eeec8`; manifest SHA `c947689e327a60cbd4a0e805978d5b13d050a612d065ac5ece6ab5481fe5e6c8`; runner SHA `9a79d09848d5bd54a00fe0199f7b2389e42fd2e2b188e6995260983b895f9a1d`.
- Independent prelaunch approval SHA `e38f235ea712e9733f1679c2accad4ed7ba03d8a604a489b500e1de9efd4d384`; actual SSH5 `-PreflightOnly` receipt SHA `ba71f66478a439661e31c4537b54970788a5e07df73aa258720e5a54c9585867`.
- Invocation SHA `81059a0b6b38378c2368c46158317b858ed16f68ebfd9bc79e220510b2f7071e`; closure SHA `3715388705404b8a78f92b9201433ebd1b4660a8c9628a5e2d39e45b6367924f`; failure-seal SHA `584e65809959f086a30c6d67f3797e9009d861253ffcd9d178fe3714d64dde99`.
- Independent standard-library audit [independent-failed-run-audit.py](./independent-failed-run-audit.py), SHA `3095aa2feeac62401be63847153f583376e10733debc4d85c2f2e7680118307`, exited 0. It independently checked all 809 manifest source SHA/size records, source maps before/after, eight closure raw SHA/size seals, ten failure-seal file SHA/size records, stage order, run identity, and absent later artifacts. The audit's `NO_GO_RUN` is the expected finding, with zero audit-integrity failures.
- Root's separate read-only freeze proof is `tmp/c09-var02-v106-failed-run-freeze-20261007.json`, SHA `e0d3825b3fb62e6995377a263aa6fad20d86c929e6990db5776c0998c85122c5`. Its postrun guard observed the original protected GUI, a free native mutex, and no remaining runner. These later live observations are custody context, not child behavior evidence.

## Stage finding

`steps.json` records import PID 2896 and export PID 11828 in SSH session 0, both `completed`, exit 0, with the GUI preserved. `import.log` records 32 inserted forms; `export.log` records completion. The Python roundtrip checker PID 10552 ran in session 0, its stderr file is empty, and `roundtrip-validation.json` says `passed: true`, `issues: []`, and 25 authored row tables. Its embedded input/export SHA values match the sealed raw files.

The same checker step is recorded as `failed` with `exit_code: null`. The frozen runner assigns `$step.exit_code = $check.ExitCode` after `WaitForExit()` and then rejects any value other than 0. The observed null therefore triggers `check_import_export rejected result` even though the output JSON reports a pass. The process exit status was **not captured as a verified integer 0**; stdout and empty stderr cannot establish it. The closure and failure seal preserve that exact error. No `model.sxo`, `model.log`, `run.log`, `report-raw.json`, or author behavior verdict exists.

## Recovery boundary

Preserve this v106 run, approval, runner, checker output, closure, and failure seal unchanged and excluded. A new version with a fresh run ID can repair the checker-process exit capture. Before any new native launch, exercise the **same production helper under actual SSH PowerShell 5** with harmless Python processes that exit 0 and 7, plus a missing or null exit-status case. It must accept only a verified integer 0 and reject both nonzero and missing status; a passing JSON body alone must not advance the runner. Then require a new frozen source bundle, exact independent static review, actual pure SSH preflight, and version-specific approval. No v106 native rerun or retrospective shortage acceptance follows from this diagnostic.
