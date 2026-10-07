# Hash correction for the frozen v106 NO_GO_RUN memo

The frozen [independent-no-go-run-2026-10-07.md](./independent-no-go-run-2026-10-07.md), SHA `50535f98d8aa4e31f934a30eb124b54a5257dad384341c6f8f595142b5fb2b54`, contains one mistyped literal for `independent-failed-run-audit.py`: it omits the `6` immediately after `...10733de`. The printed value has 63 hex characters and is not a valid SHA-256 digest.

The actual unchanged [independent-failed-run-audit.py](./independent-failed-run-audit.py), independently rehashed from disk, is **SHA-256 `3095aa2feeac62401be63847153f583376e10733de6bc4d85c2f2e7680118307`**. The original memo remains untouched. Its NO_GO_RUN decision, evidence checks, and recovery boundary are unchanged. Any later evidence index or contract should pin both the original memo SHA and this correction, and use the full actual audit-script SHA above.
