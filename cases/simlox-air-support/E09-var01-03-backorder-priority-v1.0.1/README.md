# E09 backorder priority, station-selected reports

This package evaluates E09.var01–03 in one fixed-seed, three-arm SIMLOX 2017 experiment. It derives from the accepted E12.var02 two-fault control, with one opening spare at BASE-01 and none at BASE-02 or DEPOT-01. BASE-01 consumes its local spare at h10.7579 and queues ordinary depot replenishment. BASE-02 has an aircraft-blocking backorder at h11.5 and adds a second depot request. Both remain outstanding until the first failed LRU is repaired at h14.9246.

| Arm | Control.ENBOP | Depot BOPRI | First repaired LRU to | Second to | BASE-02 ready |
| --- | --- | --- | --- | --- | --- |
| FIFO | Y | N | BASE-01 | BASE-02 | h17 |
| Priority | Y | Y | BASE-02 | BASE-01 | h16.2579 |
| Disabled | N | Y | BASE-01 | BASE-02 | h17 |

The disabled and FIFO event logs are byte-identical. The first two physical LRU movements, backorder queue and removal events, and selected half-hour `ItemResults` rows explain the allocation difference. All three arms have the same `ResultSummary`: two successful and four aborted missions across both aircraft. The priority result is therefore a timing and recipient result, not a mission-success improvement in this horizon.

The three inputs have `Item.TRACK=Y` and half-hour `ResultCollection.ITEM` rows. A guarded SSH session-0 run imports, exports, calculates and writes the default report for each arm. A separate guarded report-only run exports each sealed SXO with selectors for DEPOT-01, BASE-01 and BASE-02. Each of the nine selected reports has 72 station-specific rows. `validate_reports.py` compares all `STOHA` and `NBO` bins with the complete event interval ledger, including the later h23.4473 and h35.5 replenishment requests. `STSZ` is nominal stock, while `STOHA` is average physical on-hand over each bin; aggregate `StockTotalResults.NBO` is not the sum of all station backorders in this case. The run closures are local in ignored `runs/`; source code and the closure hashes are published in `evidence-index.json` after review.

The v1.0.0 predecessor is an excluded diagnostic: its default report had no per-station `ItemResults`. This version repeats the native run after a frozen input/reporting delta and adds independent selected exports. The result is bounded to one seed, two bases, one depot, one item type and the first two competing inbound repairs. It does not establish a general urgency tie-breaker, another demand mix, GUI behavior or cross-engine parity.
