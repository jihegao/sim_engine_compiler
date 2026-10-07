# Author probe addendum

The first author handoff retained `self_check.py` and `author-self-check.json` with 13 semantic rejections. Independent inspection identified frozen contract probes those fixtures did not directly exercise. Their exact bytes remain preserved and are not presented as complete contract coverage.

`self_check_v2.py` invokes the same production replay and event/report/pin gates after the original 303 source-pin checks and 48,684 cell comparisons. Its deterministic `author-self-check-v2.json` records 24 rejections. The added probes change a fractional SystemResults, ItemResults or StockTotalResults value beyond its predeclared printed-edge bound; swap receipt/backorder-clearance order at h10.5 or h15.1667 and fit work/completion order; insert an unallowed future lateral choice; and corrupt the model.log, closure.json, invocation.json or station-selector seal in memory. No accepted file is changed by a probe.

An intermediate v2 fixture failed because the future parent's station key is `base-01` while the current parent's key is `base01`. The exact failed fixture and stderr are in `preserved-development/fourth-failed-self-check.py` and `fourth-self-check-stderr.txt`. This was author fixture development, not a native or independent replay failure. The corrected v2 result was reproduced twice from unchanged sealed raw.
