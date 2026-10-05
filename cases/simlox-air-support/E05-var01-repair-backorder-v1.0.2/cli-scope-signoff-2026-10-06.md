# E05.var01 thirteen-hour local repair and backorder: CLI scope sign-off

**Decision:** `native_behavior_accepted_cli_scope`; approved for reusable publication on `simlox/main` for this one fixed-seed local repair-supplied backorder contrast. The [independent read-only review](review/independent-static-postrun-2026-10-06.md) returned `GO_BOUNDED` with 603/603 checks. The v1.0.0 and v1.0.1 prelaunch candidates remain excluded with their original bytes and NO_GO reviews; neither has a native child run.

## Frozen source and execution

The accepted [E05 parent](../E05-local-repair-reissue-v1.0.0/cli-scope-signoff-2026-09-29.md) supplies one LRU and a one-hour local direct repair with no backorders. Parent input SHA-256 is `ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca`; parent sign-off, closure and all 12 raw seals match. This child changes only `ItemRepair` record 1 `TEACH-LRU-01/BASE-01` `DIRPT` from 1 to 13 hours. Child [input](native-input.json) SHA-256 is `5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08`; [contract](contract.json) SHA-256 is `6dca432a09bc441544f21c69aa9f7232bff1c5ebdb430145a9de04e32a4b6d94`. Installed SIMLOX executable SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.

The unique native run `e05-var01-repair-backorder-v102-ssh-20261005-01` used SSH session 0, `Global\SimloxIssue18NativeQueue`, and the protected GUI PID 13340/session 1/start `2026-09-28T10:09:56.8261381Z` guard. Import, export, calculation and default report export completed with exit 0 while the GUI survived every step. All 20 row-containing authored tables roundtripped exactly before calculation. Converter summary was 0 errors, warning #108 only, 0 notes; SXO, event log and report are nonempty. The GUI's visual content was not sampled.

The [evidence index](evidence-index.json) SHA-256 is `d0d577a4417c7965af749bebf677f1165fbf8e46128a0aa2fc3d5f46f2718d79`. It pins the 13 original raw file size/hash seals, invocation SHA-256 `a2a7b781ee42bb8876867fcd51f620273abb8c69a3b5c36633257b3f6871fa93`, closure SHA-256 `7b92417bd273551a1cbb62a147e743436300a2b5604e925014e4a8a456148b84`, and before/after source hashes. The event log SHA-256 is `62945648448716888f44a7eb76b522e083242fd4b99623ca91c38d573ab39cb9`; original default JSON report SHA-256 is `5c80951534bb5c5ea0b1fb768cd37459f7f002f356c47bf655fb765ab171c27a`. Its trailing commas were normalized only in parser memory. Native raw files remain in the Git-ignored local run directory.

## Observed local repair and shortage

| Event | Cycle 1 | Cycle 2 | Cycle 3 |
| --- | ---: | ---: | ---: |
| Critical LRU failure | 9.25527 | 21.9597 | 33.3079 |
| Demand | 9.75527: stock ID0 issued | 22: backorder added | 33.8079: backorder added |
| Failed item starts direct repair | ID1 at 9.92193 | ID2 at 22.1667 | ID3 at 33.9746 |
| Replacement receipt | ID0 at 9.75527 | repaired ID1 at 22.9219 | repaired ID2 at 35.1667 |
| Printed backorder wait | none | 0.921933 hour | 1.35874 hours |
| Fit/SURP complete; system ready | 10.2553 | 23.2553 | 35.5 |
| Removed-item repair finish | ID1 at 22.9219 | ID2 at 35.1667 | ID3 due beyond hour 36 |

The first removed item's 13-hour direct repair clears the hour-22 demand; the second clears the hour-33.8079 demand. Each backorder is tied to its specific SURP task, received physical stock ID, printed wait, fit subtask and system recovery. The third removed item remains in repair at the hour-36 horizon. The complete event stock ledger has zero on-hand spares and zero open backorders then. All 72 half-hour SystemResults and StockTotalResults bins reconcile with the event intervals: three failure counts, three stock demands, and approximately 2.280674 aggregate backorder-hours. The last bin shows `NSYRY=1`, `NSYUA=0`, `NBO=0`, `PNB=1`.

## Replay, limits and publication boundary

The [author replay](review/author-replay-v102.json) passed 814/814 checks with SHA-256 `59a8f5a122c50effe1702cca157d915853bdefa6d6703fa0cf841fc3c228e5d7`. The separate [independent replay source](review/independent_replay.py) SHA-256 is `2629848d0f5dd4a520ffa6dce50fe5e778ec464b9a833bd5accfde02d91c1646`; its [review](review/independent-static-postrun-2026-10-06.md) SHA-256 is `8e22b2f8042b1f0e1493fc876a6fc96a6faa1332866ee78134423929f2502058`. It checked source/raw seals, task and item event lineage, all 72 bins in both reports and the terminal state without importing the author checker or invoking SIMLOX.

The CLI log identifies each failed LRU through demand, removal, repair and return, and each replacement stock item through issue/receipt and fit task. It does **not** map a fitted receipt ID to the physical ID later installed in the aircraft. Post-fit installed physical identity, cross-cycle installed-ID continuity and terminal installed physical ID remain unverified; terminal fit receipt ID2 and ready state are separate observations. `StockTotalResults` is an aggregate interval report, not an item-level stock ledger. This case establishes no general 13-hour threshold, FIFO law, other seed/turnaround value, remote supply, reorder, resource, GUI, cross-engine, performance, full E05 or full Issue #18 claim.
