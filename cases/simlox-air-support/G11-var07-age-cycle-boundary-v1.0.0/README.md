# G11.var07: first CAL100 PM below, at and above one cycle

This bounded pair derives from accepted G11.var01 fixed system prelife. Both arms deploy three identical aircraft with one `CAL100` system PM, seed 1, a 104-hour horizon and three referenced OperationProfile rows set to `IQTY=0`. The control assigns fixed CALHOURS ages 60/120/120; the boundary arm assigns 60/100/120. Only the middle `PrelifeData.AGE` cell (120 to 100) and description differ between arms.

Both guarded native CLI runs completed with zero converter errors/notes, warnings #108/#126 only, and exact roundtrip of 20 populated authored tables each. The native Prelife Logs show the frozen ages and PLINDs. In the control, aircraft ID0 first starts `CAL100` PM at h40 and IDs1/2 at h80. In the boundary arm, ID0 starts at h40, ID2 at h80 and the exact-age-100 ID1 at h100; **none starts at h0**. Every PM completes one hour later. Each arm has 208 half-hour System/Stock report bins, three PMs, no missions, resource or stock demand, and terminal ready=3.

The [contract](contract.json), [source diff](exact-diff.json), [evidence index](evidence-index.json), [author replay](author-validation.json), [independent verdict](independent-verdict.json) and [CLI sign-off](cli-scope-signoff-2026-10-03.md) define the observation. Local raw native files stay ignored in `runs/`; the index lists 26 raw hashes and sizes. Author replay passed 190/190 checks, and an independently written read-only replay passed 21,430/21,430.

This verifies fixed top-level CALHOURS ages 60/100/120 against `PMINT=100`, one seed and the first PM within h104. It does not establish the rule for other PM types, operation counters, later cycles, item prelife, GUI visual behavior or another engine.
