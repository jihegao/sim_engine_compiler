# Independent staged publication review — A01.var01 sum-one v0.1.0

**Decision: GO_BOUNDED** for the staged, source-bound publication. Reviewed 2026-10-06, before commit or PR. No native run was made. This memo is intentionally outside the package evidence index.

## Staged and sealed evidence

- Branch `codex/simlox-a01-var01-sum-one-20261006` stages exactly 25 intended paths: 24 package files and one `publication-index-v1.json` update. No raw run or product-main path is staged.
- All 22 package-relative evidence-index source size/SHA-256 pins match both disk bytes and staged Git blobs. The index itself has SHA-256 `4ede9d1078be7c3e64d47def072615865914ed9cea9ce0cd1a52e581b259acf0`.
- All 58 local raw artifact seals match size and SHA-256: 34 accepted A01 parent artifacts, 12 published TFOUT=0 sibling artifacts, and 12 new child artifacts. The sibling and child invocation/closure pins also match. New child closure SHA-256: `3cf082ca278f91d4afb0b63b0a4bbc2de560e62c6574966e0fb67a62e4500b4e`. The child's before/after source hash maps are identical.
- The child invocation records the unique run ID `a01-var01-sum1-v010-ssh-20261006-01`, SSH session 0 with `sshd.exe` ancestry, queue mutex `Global\\SimloxIssue18NativeQueue`, and preserved GUI PID 13340 in session 1. All five steps (import, export, roundtrip check, calc, report) completed with exit code 0 and `gui_preserved=true`.
- The repository-wide staged source audit reports 343 indexes, 4,539 pins, `disk_bad=git_bad=git_missing=0`.

## Source and behavior

- Direct recursive comparison with the accepted A01 input finds exactly one changed cell among 155: `MissionType.TFOUT` 0.25→0.75; `TFRET` remains 0.25. The independent contract/prelaunch review is GO and source-pinned. Accepted parent and sibling evidence are reused without rerun.
- The new native model log places the task start and completion markers together at h9.5 for aircraft 0, followed by successful mission completion at h10. This is a same-timestamp observed event ordering for this fixed mission and seed.
- The child and both accepted comparators have byte-identical raw reports (SHA-256 `b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099`). Direct parsing confirms 72 SystemResults rows × 40 columns, 72 StockTotalResults rows × 16 columns, and one ResultSummary row × 11 columns. Thus every reported non-description cell is equal.
- Staged author result is 4,130/4,130 with no failures; the separately authored a17 result is `GO_BOUNDED`, 4,504/4,504 with no failures. Their staged SHA-256 values are `233301542a7ad235e8a324a6f6363b9addbe9218908b71fb1ce8f68d14b960b2` and `5bbe151775eda62fe264110fafa09d41dcd70940e02a8e904bb57e77a9daee83` respectively. These verdicts corroborate the direct raw and source checks above.

## Publication scope

The staged publication index has 447 unique entries; the previous 446 entries and all non-entry metadata are unchanged. The sole new entry is `A01.var01.sum_one_fixed_mission.0.1.0` and confines the claim to this fixed mission, one aircraft, and one seed. It does not establish a general TFOUT/TFRET law, TFRET-zero behavior, or GUI behavior. The signoff (SHA-256 `3dbc766842d988f03b6973337d0437db671c1a5e2a15ce5c5e18e5c7a3d97f51`) uses this bounded scope and points to the verified evidence index. No publication blocker found.