# I07.var09 pre-native fingerprint failure

The first SSH session-0 invocation used run ID `i07-var09-time-to-stock-v100-ssh-20261005-01` and stopped at the immutable-source fingerprint gate, before run-directory creation or any SIMLOX child process. The runner and contract pinned the accepted E15.var01 v1.0.1 signoff as a 63-character typo `b875964c50598dda9b65dbebb66d9339fa560cf5846b8abc3c345014adbaa52`. The actual 64-character SHA-256 is `b875964c50598dda9b65dbebb66d9339fa560cf5846b8abc3c345014adbdaa52`. GUI PID13340/session1/start remained unchanged. This is a tooling preflight failure, with no native behavior evidence and no raw run closure to publish.

The corrected frozen contract and runner use run ID `i07-var09-time-to-stock-v100-ssh-20261005-02`; reviewers must recheck them before the first native call. The original independent/static preflight memos for the first hash are retained as historical review, not approval for the corrected runner.
