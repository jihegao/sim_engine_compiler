# I03.var01 CLI scope signoff — 2026-10-05

**Candidate scope:** planned personnel P-CREW OUT to `<OUTSIDE>` while busy, followed by one scheduled IN with TFDT0.5, in a fixed C03 two-aircraft model with two scheduled formation waves. C03 staffing-2 and C08 remain pinned prerequisites. This candidate is not a general I03 acceptance.

The guarded session-0 SSH run `i03-var01-crew-transfer-v100-ssh-20261005-01` completed 12/12 import, export, calculate, and report steps. Each arm had zero converter errors, two classified warnings (108 and 126), and zero notes. All 21 row-containing authored tables in each arm, including the control's all-null `ResourceTransfer` placeholder, match their native roundtrips by column names, datatypes, and rows. The closure seals 32 raw files and shows source hashes unchanged. The protected session-1 GUI identity was checked before and after every native child.

The raw events establish a h7.75 OUT backorder, no premature removal of busy crew, and one-crew OUT fulfillment at h8. The first formation launches at h8 and completes at h9 in all arms. The `out_in` IN starts at h10, arrives at h10.5 after TFDT0.5, and restores two crew. The second formation launches at h20 in control and `out_in`, and at h20.5 in `out`; the half-hour delay matches serial crew preparation and `ResourceResults` bins. All three reports have 72 consecutive half-hour `SystemResults`, `StockTotalResults`, and `ResourceResults` bins; aircraft conservation, zero failures/damage, and terminal readiness reconcile with the event logs.

The author replay is `review/author-validation-2026-10-05.json`; the separate read-only replay and verdict are `review/independent_replay.py` and `review/independent-verdict.json`. Publication requires that independent verdict to pass. The native report's single trailing comma is normalized in memory only; raw bytes and hashes remain unchanged.

**Limits:** one seed, one station, personnel only, one OUT and one IN schedule. No BETWEEN, equipment transfer, general resource-priority rule, GUI, cross-engine, or full Issue #18 claim.
