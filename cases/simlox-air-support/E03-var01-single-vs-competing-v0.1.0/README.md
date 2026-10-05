# E03.var01: one mission demand versus E03 competition

This bounded CLI variant changes accepted E03's one `OperationProfile.IQTY` cell from 2 to 1. Two aircraft remain deployed with one opening local LRU spare. The source description also names the child. The [contract](contract.json) and [exact parent diff](parent-diff.json) define the source boundary.

The guarded native run launched one mission and observed one installed LRU failure and replacement demand. The opening spare was issued without a backorder; the failed item was removed, repaired locally, and returned to stock. See the [dated signoff](cli-scope-signoff-2026-10-06.md) and [evidence index](evidence-index.json) for the exact accepted scope and byte pins. The original author replay failure is preserved in `review/author-replay-v010-failed.json`; the separate v0.1.1 checker corrects its ready-list ordering assumption. Independent review checks every report interval.

Run `python build.py` to verify the frozen source input and `python check_parent_diff.py` to inspect the two changed cells. Native outputs remain in the ignored local `runs/` directory and are sealed by SHA-256 in the evidence index. No accepted parent run needs repeating.
