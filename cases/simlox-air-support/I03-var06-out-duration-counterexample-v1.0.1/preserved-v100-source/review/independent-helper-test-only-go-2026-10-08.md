# GO_TEST_ONLY — I03.var06 binary process capture

This decision permits **one harmless SSH session 0 / Windows PowerShell 5 `-File` test** of `test_captured_process.ps1` in a new output directory. It does not permit a SIMLOX child, the case `-PreflightOnly` call, or native execution. Root owns the invocation and must keep the protected GUI and native queue untouched.

Exact candidate files:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `captured_process.ps1` | 9,028 | `17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794` |
| `test_captured_process.ps1` | 4,951 | `22112fc0decf89fa8b704b4c47ea1397f090b6e042895122ca8f28abc94f9ac8` |
| `binary_capture_child.py` | 842 | `52f28d5d705efad0fa035ab5031a96da5fa6a27571a2d9bb8f46648e5800c35e` |

The local Windows PowerShell 5 test receipt at `C:\Users\user\Models\simlox-spike\capture-test-v4-20261008\receipt.json` is 4,969 bytes, SHA-256 `bc3d5e0cc43b7f64fd27de1769688a0ac3e5d52e04ac9e72702a4d536b6d7914`. It reports five real local session 1 child PIDs with integer exits 0, 7, 0, 0, 0. The injected session observation, synchronous drain setup, and asynchronous stdout drain faults retain `capture_error` and fail the production success predicate. The asynchronous case emitted 1,310,720 bytes on each stream; the original binary SHA and size matched. Seventeen malformed record mutations were rejected. The ordinary zero-exit path retained invalid UTF-8 bytes, NUL and CRLF without decoding and reencoding.

The helper now starts both binary stream drains and joins the started child naturally; recoverable drain faults are detected before `WaitForExit` and retried into the original files. A persistent OS or file-stream failure that makes every drain impossible is outside this local fixture's proof and must never be classified as a successful native step. The actual SSH0 test must independently establish its own process session, integer exits, binary hashes, joined injected failures and no SIMLOX child. Its receipt must be reviewed before any case preflight or native approval.
