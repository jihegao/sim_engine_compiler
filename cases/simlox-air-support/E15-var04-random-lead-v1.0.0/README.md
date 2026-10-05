# E15.var04: one sampled random reorder lead

This package adds one source cell to the accepted E15 explicit-three stock-based DU depot model: `ItemReorder.LEADTD` changes from null to predefined `<EXP>` while `LEADT=1` hour remains the mean. The accepted E02 prerequisite is pinned through the parent. The installed SIMLOX 2017 manual, physical page 345, permits this combination.

The guarded session-0 SSH run sampled 1.12383 hours for its single h10 two-item order. Delivery completed near h11.1238, adding physical IDs 5 and 6. Depot on-hand was 3 before the h10 issue, 2 until delivery, then 4. The selected half-hour report records 3.50469446 as the time-weighted on-hand value for h11–11.5; its horizon mean is 3.65978742. All other selected report cells match the accepted fixed one-hour parent. The run preserves 13 local raw file seals in ignored `runs/` and validates one sampled lead, not the exponential population law.

Run `build.py` to verify the frozen child input, `validate_native.py` for author replay, and the independent script in `review/` for a separate read-only replay. The contract, source SHA pins, raw evidence index, and signoff define the exact bounded acceptance. GUI-only behavior, cross-engine equivalence, multiple orders or seeds, and full E15.var04/E15/Issue #18 remain unverified.
