# G11.var08: top-level Prelife.MID wildcard for one system type

This bounded pair starts from accepted G11.var07 equal-boundary input. Both arms deploy three `TEACH-AIR-01` systems through `PL-SYS`, with fixed CALHOURS ages 60/100/120, CAL100 PM, seed 1, a 104-hour horizon and referenced profile `IQTY=0`. The only business change is `Prelife.MID` from `TEACH-AIR-01` to literal `*`; descriptions label the arms.

Both guarded native CLI runs completed with zero errors/notes and only warnings #108/#126, exact roundtrip of 20 populated authored tables each, and 13 sealed local raw files each. Their Prelife Logs are byte-identical and name the actual `TEACH-AIR-01` systems at ages 60/100/120. Event logs are byte-identical: ID0 first CAL100 PM h40, ID2 h80 and ID1 h100, each one hour, with no h0 PM. ResultSummary, SystemResults and StockTotalResults are equal. Each arm has 208 half-hour System/Stock bins, terminal ready3 and no missions, resource or stock demand.

The [contract](contract.json), [source diff](exact-diff.json), [evidence index](evidence-index.json), [author replay](author-validation.json), [independent verdict](independent-verdict.json) and [CLI sign-off](cli-scope-signoff-2026-10-03.md) define the evidence. Raw native outputs stay in ignored `runs/`; the index records 26 hashes and sizes. Author replay passed 193/193 checks and a separately written read-only replay passed 21,433/21,433.

This establishes top-level wildcard acceptance and equivalence for one system MID and PLID only. Matching multiple MIDs, StockAllocation use, sub-prelife invalidity, other PM counters, GUI visual behavior and cross-engine parity remain unverified.
