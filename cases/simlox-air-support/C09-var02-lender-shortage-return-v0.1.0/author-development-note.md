# Author checker development note

This records a **new retrospective checker draft** failure, separate from the frozen v1.0.7 native failure and independent review. No native call or raw edit occurred during this development step.

The first draft compared exact counts of differing cells in the two raw reports with exact counts in the two unrounded source/event oracle dictionaries. It rejected with observed table counts `ProblemDescription 1, ResultSummary 0, SystemResults 12, StockTotalResults 0, ResourceResults 6, ResourceResultsTotal 4` versus oracle raw-float counts `1, 0, 12, 0, 6, 5`. The extra oracle difference was `ResourceResultsTotal.NRUM`: printed-time integration gave approximately `0.14583500000000008` for the control and `0.14583333333333334` for the child, while the two native report cells were identically `0.1458333283662796`. Both report values independently passed the predeclared per-arm numeric bounds. This was an author diff-count gate error, not a native result failure.

The corrected checker first compares all 1,754 cells per arm to source/event-derived values under the frozen field-specific bounds, then checks the six **observed** diff counts as a descriptive cross-check. It separately reports the unrounded oracle float diff counts so the small NRUM discrepancy stays visible. It does not fit a tolerance to the observed child report or promote the original prospective v1.0.7 NO_GO_RUN.

The first draft checker bytes and its failing output were not saved to files before correction; this note records the available failure tuple and cause, and makes no claim to preserve an unavailable full draft file or transcript.
