# F03.var04 bounded native CLI scope signoff — 2026-10-04

**Decision: ACCEPT one fixed-seed two-base lateral peer comparison for simlox/main.** This establishes physical stocked-peer substitution for the first matched BASE-01 LRU demand under the accepted immediate lateral rule. F04, autonomous stations and Issue #18 remain open; product main stays separate.

## Frozen sources and execution

The accepted F03.var03 [parent input](../F03-var03-demand-location-v1.0.0/risk_base1-input.json) SHA-256 is df4daeab5076e4b29b2d2a04c0a90bddd0af589af1e0dce2483c48fce5c2a06c; its native closure is d759fa4d7bc7992c4d5d27c695a5809d28d06fa47c1e2e1a86d733c5d4395cc9 and signoff SHA-256 is 3bc03e7fe062df611dfdebbbc3da3845b97f6776a0a2477c13b0cd47dc543b1c. The accepted E08 donor input SHA-256 is 630d7600e7ff77ddb057f05af0852b4f41ed6335718570f9fcf5eddd9f51c474 and signoff SHA-256 is 62811d4761a05c7aea45e6b9514a6865d2ca54ca8a07d655ee656ddbad1e5986. The [contract](contract.json) SHA-256 is 6093d3d63bcc683d8dad34c3f69a9d10259a8caf94b17d13590cf561dc7a7d1c.

The [ON input](lateral_on-input.json) SHA-256 is 470214d017cc149077b4a96b37573dd8b32f435ca45b571a3ea5c171bd2c4cbe; the [OFF input](lateral_off-input.json) SHA-256 is f1466be0ecdf7fcc2edab029a81a61db4acf873dad4b478d0e28be4d54231e4b. The [exact diff](exact-diff.json) SHA-256 is 0f76d6fe560103467b9eff7a47b4af38659fe7628a48217a4f15ba869fb37f09. Both children retain the same three-aircraft risk fleet, 60-hour horizon, two-hour depot routes, LAT-01 BASE-01/BASE-02 peer group, BASE-02 one opening LRU, immediate lateral rule and 0.5-hour peer transport. The sole paired business change is Control.ENLAT Y/N.

Two serial guarded session-0 SSH runs held the host mutex, verified sshd ancestry and preserved active GUI PID 13340/session 1. ON run f03-lateral-on-v100-ssh-20261004-01 closure SHA-256 dba6d8f4a0a1c209edd32273a0ea517604727c4d68fb8726191c6ca9ff0f7ad9; OFF run f03-lateral-off-v100-ssh-20261004-01 closure SHA-256 d0d59aaf06745d84f49b53553174124e23e4584d0419499971e898add1966e88. Both completed native import, export, calculation and report, exact roundtrip of all 31 authored populated tables, and converter Errors 0, reviewed Warning #108 only, Notes 0. [Evidence index](evidence-index.json) SHA-256 b5b2a3921463e4567f0aeec08ecebb2239dfa70b9724ea4e3dae7fb4e775f752 seals 24 ignored local raw files, closures and source/reviewer records.

## Observed outcome and review

The first risk fault h22.24 and BASE-01 demand h23.74 match. ON physically takes LRU item 4 from BASE-02 at h23.74, transports it to BASE-01 in 0.5 hour, and clears the backorder h24.24. Depot LRU item 2 replenishes BASE-02 at h25.74. OFF does not issue from the peer: depot item 2 travels to BASE-01 in two hours and clears its backorder h25.74. The same aircraft's first repair completes h24.5733 ON versus h26.0733 OFF; its unit's first BASIC mission starts h25.0733 versus h26.5733. The BASE-02 unit's mission succeeds h8–10 in both arms.

All 120 half-hour System, Stock and Resource bins reconcile with event-derived aircraft counts, stock backorders, worker leases and queues. Both runs terminate with three ready aircraft, no backorder and no worker queue. Whole-run backorder item-hours are one ON versus six OFF; these are descriptive totals. Later random fault paths diverge (ON h46.8394, OFF h46.7231), so later outcomes and whole-run differences are not a matched-fault causal estimate.

[Author replay](author-validation-2026-10-04.json) passes 538/538, SHA-256 59776733b5ac6ef74884e3f22be15aed040d78b12fa8337fc5a52d8ccccc6b87. Separate read-only [independent replay](review/independent_replay.py) SHA-256 8da4d8f9531379902256e508f9456e000a8e386718d280f52ae188a0cd300153 returns [GO, 1,806/1,806](review/independent-verdict.json), verdict SHA-256 8c9d93641353f83cbe53b2b9da71f99be0bbf8eee502ff73d17806ce4a917941. [Independent static preflight](review/static-review-2026-10-04.md) SHA-256 0303b2451ace2ee3995eec5fbba048741b5e82ddf4a8003498658100569b6bcc cleared the frozen pair and native safeguards before execution.

## Scope boundary

One seed, two bases, three aircraft, an IMMEDIATE lateral rule, 0.5-hour peer route and one matched first demand are established. Autonomous stations, alternative lateral policies, overlapping demands, contention, other seeds, GUI behavior and cross-engine equivalence remain unverified. F04 and Issue #18 remain open.
