# C04.var03 v0.1.0 independent read-only replay

**GO_BOUNDED — 11,153/11,153 checks, zero failures.** The separately authored checker uses only the Python standard library and accepted raw files; it does not import or copy the author checker and does not invoke SIMLOX or the GUI. Two runs produced byte-identical LF verdict JSON.

| Artifact | SHA-256 |
| --- | --- |
| Frozen contract | `8430c74254baae1401edb92df41f1dee0ae7a30c9628e5f21b2d56197bd34d3d` |
| Independent replay script | `cefd2a3fd02c5aa874df61b6156181587ff0816011541230b9b20de50b478581` |
| Independent verdict | `d4527fce3b2e900c3ce8eb24e38c75bee8602d66e463981d90c1e23d45266987` |

The replay verified the installed manual; all 25 accepted C04 source local and Git identities; four published C04.var02 overlap source local/Git identities; direct C03 parent source, invocation, closure and 11 raw SHA/size seals; and both selected final C04 input/diff/invocation/closure chains and 22 raw seals. It rechecked the excluded horizon-wait #107/#204 log and four-byte invalid SXO. Each selected native invocation records SSH session 0 with `sshd.exe` ancestry, global mutex, GUI PID 13340 responsive in session 1 at preflight and the same PID/start identity checked by the accepted runner after four ordered, successful import/export/calc/report stages. No fresh GUI state is claimed.

The source pair has identical 31-table structure, 979 scalar leaves and 201 authored row cells. Its **sole** difference is `OperationProfile.DTIM 0.50→0.49`, with STIM8, two aircraft and one shared P-CREW fixed. Native exports preserve every authored row-containing table; null-only native placeholders are classified separately.

In both traces, aircraft ID0 uses crew h7.5–8; aircraft ID1 receives/books the released crew and starts its planned half-hour subtask h8. In the control, ID1 completes and frees the crew at h8.5 before the two-aircraft mission launches and later succeeds h9.5. In the partial arm, the mission cancels h8.49 while ID1 is active: ID1 is ordered to stop, its task and preparation stop, **no ID1 subtask completion** occurs, the log records ID1 factor 0.98 versus ID0 factor 1, the crew is freed and deallocated **once**, and both physical IDs arrive ready. Resource waiters are zero at h8.49; there is no launch or mission success.

The checker parsed only private trailing-comma-normalized report copies and verified all **10,420 cells**, including null/string values, six table shapes and 72 half-hour interval grids. It independently compared the equal-arm report's 5,210 cells against accepted C03 staffing-1 and reconstructed every partial-arm field from that baseline with the event-derived changes. The changed-cell counts are exactly `0/4/15/0/1/1` in ProblemDescription, ResultSummary, SystemResults, StockTotalResults, ResourceResults and ResourceResultsTotal order. The h8–8.5 fractional ready/preparing/crew-use values and terminal ledger reconcile; all stock cells remain equal.

This is an owner-level catalog reclassification of the **same accepted runs** previously examined by C04.var02. It strengthens the focal absence/exact-once checks but adds no independent native observation. The 0.49/0.50 comparison to logged factor 0.98 is source-bound, not a general turnround formula. No structured cancellation reason, universal same-time rule, GUI-only result, cross-engine parity or full Issue18 acceptance is inferred.
