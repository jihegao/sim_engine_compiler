# G11.var09: two same-type mothers with different installed child ages

This bounded pair starts from accepted G11.var04 installed-item inheritance. Two deployed `TEACH-AIR-01` mothers each have a separate SYS→POS→LRU Prelife path. Both system ages are 60 CALHOURS; leaf ages are 20/60 in one arm and 60/20 in the other. The pair changes only those two `PrelifeData.AGE` cells plus description. It keeps one monitored CAL100 LRU per mother, one stocked spare, seed 1, `IQTY=0`, and a 96-hour horizon.

Both guarded native CLI runs completed five steps with zero errors/notes and only warning #108, exact roundtrip of 23 populated authored tables each, and 13 sealed local raw files each. The Prelife Logs show distinct `SYS-A` and `SYS-B` child paths and the swapped leaf ages. In age20-then60, original LRU/system ID1 enters PM at h40 and ID0 at h80. In age60-then20, ID0 enters at h40 and ID1 at h80. Each system PM completes after 0.5 hour; removed item PM begins after 0.25 hour and completes after 1.25 hours. The first exchange issues spare ID2, the second issues the repaired first original, and both originals return to stock.

Non-description report tables are equal between arms. Each has 192 contiguous half-hour System/Stock bins, two system and item PMs, terminal ready2 and stock1, and no missions, resource booking or backorders. Numeric IDs are established by native PM and demand events; the Prelife Log itself names PLIND paths without numeric IDs.

The [contract](contract.json), [source diff](exact-diff.json), [evidence index](evidence-index.json), [author replay](author-validation.json), [independent verdict](independent-validation.json), and [CLI sign-off](cli-scope-signoff-2026-10-03.md) define the evidence. Raw native outputs stay in ignored `runs/`; the index records 26 raw hashes and sizes. Author replay passed 193/193 checks and a separately written read-only replay passed 19,024/19,024.

This establishes the observed first PM mapping for two same-type mothers with separate installed-child PLIDs. More systems, mixed types, stocked-item prelife, later PM cycles, other OPIDs, GUI visual behavior, and cross-engine parity remain unverified.
