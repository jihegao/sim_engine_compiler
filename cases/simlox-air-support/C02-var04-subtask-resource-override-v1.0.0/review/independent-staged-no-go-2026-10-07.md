# C02.var04 v1.0.0 initial staged publication review

**Decision: NO_GO_STAGED** for the initial staged snapshot with evidence-index SHA256 `c825c2a0909912f10ebc7c387ce9631f47a1b3c3c401a13579d223b1307dbff1`.

The stage has exactly 32 intended paths: 31 package files and the root `publication-index-v1.json`. No native `runs/`, product-main or unrelated path is staged. All 30 evidence-index source SHA256/size pins match both disk and staged Git blobs. The 70 frozen manifest file pins remain stable; 36 accepted C02/C01 published/local source byte identities, 33 accepted raw and 26 new child raw seals match. The old 482 publication entries and root index metadata are unchanged; the staged 483rd ID is unique. The CR-aware staged whitespace check exits zero. The preserved unapproved draft and independent 11,405/11,405 postrun verdict are accurately identified.

Two publication defects remain:

1. The new 483rd entry uses repo-root `cases/simlox-air-support/C02-var04-subtask-resource-override-v1.0.0` paths for `package`, `evidence`, `signoff` and `evidence_index`. Each of the previous entries uses paths relative to `cases/simlox-air-support/`, the directory containing the publication index. Resolving the new `evidence_index` from that directory points to a nonexistent doubled path. Use `C02-var04-subtask-resource-override-v1.0.0` and its package-relative evidence paths, then verify the 482-entry prefix and metadata again.
2. The indexed `README.md` ends, “No native result is accepted yet,” without identifying itself as a preserved prelaunch snapshot. The indexed `results-2026-10-07.md` and signoff now accept bounded postrun evidence. Label the README as a historical prelaunch snapshot and direct readers to results/signoff for the current status; preserve the frozen prelaunch manifest and native raw bytes. Regenerate the evidence index and recheck its source and staged Git pins after this documentation correction.

The bounded physical claim itself is supported by the sealed pair. These are publication-path and status-wording corrections, not requests for another native run or broader interpretation.
