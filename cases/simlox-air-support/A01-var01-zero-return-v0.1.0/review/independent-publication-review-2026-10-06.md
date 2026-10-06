# Independent staged publication review — A01.var01 zero return v0.1.0

**Decision: GO_BOUNDED** for the staged package and publication-index append. Reviewed 2026-10-06 before commit/PR. This memo is outside the evidence index to avoid a self-reference. No native calculation or GUI operation was performed.

## Staged provenance

The staged diff has exactly 25 intended paths: 24 new files under `A01-var01-zero-return-v0.1.0/` plus `publication-index-v1.json`. No run artifact, product-main file or unrelated path is staged. All **22/22** package-relative evidence-index source records match SHA-256 and byte size on both disk and staged Git blobs. Evidence-index SHA-256 is `5c821201c83254a2d26292f2917608fe722d3c7484f3b63da631097f2f4a088f`. The package `.gitattributes` preserves exact CRLF-bearing source blobs; Git whitespace diagnostics on those sealed bytes are not a source-hash mismatch.

All **70/70** local raw artifact size/SHA seals match: accepted A01 final/replay 34, published TFOUT0 sibling 12, published sum-one sibling 12 and new TFRET0 child 12. Sibling and child invocation/closure byte pins also match. Child closure SHA-256 is `4700b79d6209fc6213810cfa11760687e0fa3e294e2dc4f31532ca1f2fdc8517`, has no error and records identical before/after source hashes. It references the correct frozen contract, input, runner, independent prelaunch approval and accepted anchors.

## Source, run and behavior

Direct comparison of the staged child input with the accepted A01 input yields exactly one changed cell among 155 authored cells: `MissionType.TFRET` 0.25→0; `TFOUT` remains 0.25. The contract SHA-256 is `15afed5c5c0b344ecbbfb419a0c326dc4c5a0ed3ff8e4d180ca543b47079c987` and child input SHA-256 is `66f2c6fc9d7e4438514f4965c968e0bc3d11db824fd5682f06d1e7362a1346ef`. The accepted-parent negative control fails the child h10 timing gate. The independent contract, actual SSH0 preflight, and approval JSON are staged with their frozen byte pins; no accepted parent or sibling was rerun.

The unique child run `a01-var01-tfret0-v010-ssh-20261006-01` records SSH session 0 with `sshd.exe` ancestry, the global serial mutex and preserved GUI PID 13340/session 1/exact start. Import, export, roundtrip check, calculation and report each completed with exit code 0 and `gui_preserved=true`. The native log shows physical aircraft ID0's task starting h8.5, task completing h10, and mission success and completion h10. Both h10 markers are observed; no general same-time event-order rule is inferred. The raw default report is byte-identical to the accepted parent (SHA-256 `b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099`). Independent parsing confirms 72 System rows × 40 columns, 72 Stock rows × 16 columns, and one 11-field ResultSummary row. The staged author verdict is 4,172/4,172 with no failure; the separately authored independent replay is `GO_BOUNDED`, 4,526/4,526 with no failure.

## Index and limit

The staged publication index grows from 447 to 448 unique entries. All prior 447 entries and non-entry metadata remain unchanged. The sole new pointer is `A01.var01.zero_return_fixed_mission.0.1.0`; its scope and signoff confine the result to this fixed h8–10 mission, one aircraft, one seed and a zero-return fraction. The signoff SHA-256 is `795f4f0a7ac1c26de10bc3dbc09856626b769dec37709fbf013d4a15d2703eff`. Travel geography, general schedules or durations, GUI visuals, cross-engine behavior and full A01.var01/Issue #18 acceptance remain unverified. No publication blocker found.