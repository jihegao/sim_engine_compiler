# I01.var02: blank APID with two stock POINTs

This bounded case follows accepted `I01.var01` with a byte-identical `AIR_BASIC` selected control. The child changes only `Control.APID` to blank (`null` in the native JSON input) and ProblemDescription. Both sources still contain `AIR_BASIC` stock 1 and `AIR_EMPTY` stock 0 for `TEACH-LRU-01` at `BASE-01`.

The installed manual says a blank APID leaves **maintenance policy** unfiltered. It does not explicitly promise the same for stock. In this native stock-only model, the blank arm's converter reports notice #102, “Simulation with no stock,” with zero errors. The selected arm's event log and result report match accepted I01.var01 stocked. The blank arm's event log matches accepted I01.var01 AIR_EMPTY byte for byte; its three business report tables also match. Thus blank APID produces no initial stock in this model, despite two StockAllocation POINT rows.

The shared ordinary LRU failure occurs at h9.8829 and aborts the first mission. Selected APID takes a spare at h10, completes system replacement at h10.5, repairs the failed LRU at h11.1667 and ends ready. Blank APID backorders at h10, reuses the repaired LRU at h11.1667, completes replacement at h11.5 and ends ready. Later missions succeed in both. The blank arm has one system item-wait hour and 1.16667 stock backorder-hours; selected has zero for both. Both have 0.5 active system-repair hours and 72 aligned System/Stock half-hour bins.

Run source/diff checks with `build.py` and `describe_diff.py`; replay the native evidence with `validate_native.py` and `review/independent_readonly.py`. Raw native artifacts stay in ignored `runs/` and are sealed by `evidence-index.json`. GUI visual behavior and resource/maintenance allocation blank-APID behavior are outside this case.
