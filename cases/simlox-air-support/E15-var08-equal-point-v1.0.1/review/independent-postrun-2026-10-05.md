# Independent postrun review: E15.var08 v1.0.1

**GO, bounded to the report-only observation.** The separate read-only replay passes 531/531 checks. The excluded v1.0.0 calculation closure and all 11 old raw files remain sealed. The new SSH0 run has one successful guarded `-report` step and four sealed raw files. Its command contains no calculation or import step, and source hashes before and after match.

The original event log shows depot opening stock IDs 0 and 1 (two on hand), no h0 reorder, an h10 issue of ID0 leaving one, one h10 reorder with one-hour lead, and three new IDs 4, 5, 6 delivered and stocked at h11. The selected ItemResults has 72 consecutive half-hour rows: nominal stock 4 throughout, on hand 2 for 20 bins, 1 for two bins, then 4 for 50 bins, zero backorders and one h10 order. ItemResultsTotal mean is 3.361111164, matching 242/72 within report precision. Relative to accepted explicit-three, only the first 22 ItemResults on-hand cells and the ItemResultsTotal on-hand mean differ; the other eight selected tables match in full, including the system, mission, StockTotal and summary tables.

This accepts the observed equal-point opening stock and h10 reorder path for one depot and seed. It does not rehabilitate v1.0.0's failed h0 hypothesis or establish a general equality threshold, other stock states, or the internal ordering rule.
