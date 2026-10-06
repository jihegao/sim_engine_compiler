# Independent postrun review — A03.var01 three available

**GO_BOUNDED.** My separately authored read-only replay passed **4,382/4,382** checks against the sealed run `a03-var01-three-avail-v010-ssh-20261006-01`. I did not invoke SIMLOX or import the author validator.

The child closure SHA256 is `965ba78470846f2ad6634c3e82008dabc20a9beefb1762bba3ae0fef9a46396d`. Its 12 raw SHA/size seals pass; the accepted A03 parent closure and all 11 parent raw seals pass. The 21 child source pins match disk and remain identical before and after the run. Invocation records SSH session 0, `sshd.exe` ancestry, the global Issue18 mutex, and GUI PID 13340 in session 1 with start time 1790590196826 ms. The five ordered import, export, roundtrip-check, calculation, and JSON-report stages completed with exit 0 and preserved the GUI. Converter diagnostics are exactly Errors 0, Warnings 2 (#108, #126), Notes 0, with a substantive SXO.

The authored model has exactly one changed cell among 155: `SystemDeployment.QTYPS` 2→3. All 13 row-containing tables roundtrip exactly. The event log shows physical aircraft IDs 0, 1, and 2 ready at h0. One h7 mission requested two; IDs 0 and 1 were allocated and prepared, while ID 2 remained ready. The same pair launched at h8, performed the h8.5–9.5 task, succeeded and returned at h10. The final ready snapshot contains all three IDs. No second mission, waiting/cancellation, fault, maintenance, or stock issue was observed.

Every field in all 72×40 System rows was checked against the accepted parent or the frozen analytic prediction: `NSYA` and `NSYRY` add one in each bin; `FTMO` is 2/3 in h8–10 and zero elsewhere; all other cells equal the parent. The integrals are 108 available, 102 ready, 2 reserved, and 4 operating aircraft-hours. All 72×16 Stock cells, 11 ResultSummary fields, and ProblemDescription columns/rows equal the parent. The summary retains `NREP=1` and `MTMF=MSTF=MSUF=STMF=1`.

This supports one fixed-seed, one-wave CLI observation with one surplus aircraft. Numeric selection of IDs 0 and 1 is observed, not a general selection-priority rule. The inherited Unit description saying one aircraft is stale and is not used as physical evidence. No larger fleet, other seed, GUI visual, or full Issue18 claim follows.

Replay code: `review/independent_replay.py` SHA256 `d64a5fc68ef0fed1e425483764b13369c27fc367a0497e070a954489745c10ac`. Machine verdict: `review/independent-verdict.json` SHA256 `bdc4f11eb325b0d0411288ecc6ed146f2c0617ba247f56911f39ac8cfb34e3fd`.
