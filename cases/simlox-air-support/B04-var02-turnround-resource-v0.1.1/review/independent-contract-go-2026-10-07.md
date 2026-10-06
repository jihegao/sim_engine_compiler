# B04.var02 v0.1.1 resource-report contract amendment

**Decision: GO_CONTRACT_ONLY.** This reviews the v0.1.1 contract amendment, not the copied validator or runner. No native run is approved by this memo.

The contract SHA-256 is `eddc9b1221ac6f0c1acb4c55764bb218c61b251ca58435fb8f2f14efc3b8d49d`. Its child input SHA-256 is still `0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5`, byte-identical to v0.1.0. The parent B04.var05 input/closure and C01 capacity-two input/closure pins are unchanged. The 221-to-249-cell source plan and two resource lease hypotheses are unchanged. The reserved run ID is now `b04-var02-turn-resource-v011-ssh-20261006-01`; the v0.1.0 run directory did not exist at review.

The v0.1.0 independent prelaunch **NO_GO** memo SHA-256 `9ccf07faf96cdb1870c3b88a40071afa30e07f30346aef6dbad1455bbcc8a4ce` remains preserved. It identified a five-table report expectation that omitted `ResourceResultsTotal`; no v0.1.0 native run occurred. This contract records that history and prospectively adds full `ResourceResults` 72×16 and `ResourceResultsTotal` 1×14 checks. The accepted C01 resource report has both tables. Its total `NRUM` is a whole-window average: two one-person leases lasting 1/6 hour each give a 1/3 person-hour integral, and division by the 36-hour reporting window gives `1/108` (approximately 0.009259259). The proposed total and interval gates are coherent, falsifiable and do not retroactively accept v0.1.0.

All existing B04.var05 mission, System, Stock, summary, description, event identity, converter and source-seal gates remain. The next exact-file prelaunch review must verify a corrected validator actually enforces the six-table topology, the 14 total columns and event-to-interval-to-total reconciliation, then bind its bytes and a safe runner to the new run ID. This memo does not assess or approve those files.

**Limits:** This remains one fixed-seed sufficient-crew CLI arm. It does not establish resource shortage, contention, shifts, substitution, GUI behavior, general B04.var02 semantics or cross-engine equivalence.
