# Independent pre-run static review — E15.var07 v1.0.1

**Verdict: GO for two fresh, serial guarded native candidate runs.** This review does not accept the predicted stock behavior or authorize publication; the v1.0.0 runs remain excluded.

## Source and semantics

- The direct G01.var03 DU donor input matches its pinned SHA-256 `c409f4b210b9f60e5f36bf6b15f56aaba95f4b08b4f6b6de290b60d65086d7d9`; the E02 prerequisite matches `12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd`.
- The two v1.0.1 inputs match their contract and runner pins: default `602dedfdb3491ab430abe4c68426c28203738fe1b2b1173d5d66955d00b6102e`; explicit-three `bb57aecc7285d8eef5c71ba1b7f6b6f7dd9fb4cc46f3e6d88e863eb1da3f206f`. An independent JSON comparison found 31 source tables and 21 row-containing tables in each. Relative to G01, both change only `Item.TRACK` null→Y, depot `StockAllocation.STSIZ` 2→4 and `ROSIZ` 1→2, and description; explicit-three also changes depot `ISTOH` null→3. Between arms, the only behavioral change is depot `ISTOH` null→3. The generated `exact-diff.json` equals a fresh read-only derivation and has SHA `db9dbaa3b986896c84d9634e414d1308d0a555dbccc0831fc8768d6d4d7dc3dc`. The builder's read-only source check passed.
- Installed dictionary `Item.TRACK` is a Y/N item-result collection switch with default N. Manual stock pages 445–447 support `ISTOH` default `STSIZ+AINST` and minimum `STSIZ−ROSIZ`. With `STSIZ=4`, `ROSIZ=2`, the hypothesized opening on-hand 4 versus 3 and reorder point 2 are valid. Setting TRACK in both arms addresses the v1.0.0 report-availability failure without changing the arm contrast. The expected hour-10 issue and hour-11 batch receipt remain native hypotheses.

## Runner and evidence gates

- Current `contract.json` SHA is `704e7951cfbfb7cab9274d4f5c723c065c0b2781c2244927686082e1f74208f4`, and current `run_native_ssh.ps1` SHA is `1c9585d8334286b8f4ebf3536796c865808b0497f897a390dd02d21a13373d81`. Both literal contract and diff pins in the runner match these files. The runner also pins both arm inputs, G01 donor, E02 prerequisite, installed manual/dictionary and executable; it records source hashes before/after. Python AST checks for builder/diff/checker and PowerShell parser all passed.
- The runner requires session-0 SSH and an `sshd` ancestor, takes the global native mutex, verifies active GUI session and PID 13340 start/session identity, uses hidden processes and a fresh immutable run directory, and writes raw-hash closure. Its calc gate requires the exact zero-error/one-#108-warning conversion result before report export; roundtrip checker expects 21 populated authored tables and exact rows/columns. No native command was invoked during this review.

The copied report-only runner is outside this fresh-native launch gate and must be repinned to the new v1.0.1 SXOs and closures before any report-only export. Acceptance still requires station-selected ItemResults in both arms with 72 bins and independent reconciliation of physical item identities, reorder events, stock and system reports.

## Report-only recheck, 2026-10-02

**Verdict: GO for two serial guarded report-only exports.** The earlier report-runner limitation is resolved; this verdict concerns launch safety and selector identity, not the report values.

`report_native_ssh.ps1` now hashes to `558abd3d2e16e89fa2752cb21de1a5a9f9f4a7edfd3341ca5ce815291226ae05` and parses with zero PowerShell errors. The unchanged `make_report_settings.py` hashes to `d2ede31eba96985da2e6671ef0f81fe0d010f5e2d6889f09531519e11c73df1e` and parses as Python. Its pinned Default.sxs yields an already present local selector with SHA `841a6a077741566cac02b84e0cb35f4154f13a857e5665909a483cd6c051316c`. Independent binary parsing confirms IID `TEACH-DU-01`, STID `DEPOT-01`, and exactly SLIT/SRIT/SRTT enabled (value indices 2, 30, 32).

Arm mapping now points to fresh v1.0.1 native runs. Default closure/SXO SHAs are `f00b8fc07a4deb1db33b6142f0704e373a5db09197e8f6190fd0b22947e6feff` / `d3e67fbcb619f85f0587dc021d0957a4b7a237cefc99571ace31910cd42beed3`; explicit-three closure/SXO SHAs are `79e4729d44a4a3ed524ad9e0f0559c4d98c3aff64278bf553c3768f956c435e5` / `8fe1a580eacc9e0e7026725e4bbc2175b59ae08e21a24af1d415b97911611e98`. All match the runner literals, both closures have null errors, and each closure seals its on-disk SXO SHA. The report runner preserves session-0 SSH/`sshd`, host mutex, active GUI PID 13340 identity, hidden `-report -rpts -rjexport`, immutable run ID and failure closure guards. Actual ItemResults table presence and 72-bin stock reconciliation still require post-export replay.
