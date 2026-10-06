# C05.var02: two required mission resource types

This package maps the catalog's C05.var02 label to the already published [C05 radio-2/radio-0 native pair](../C05-var02-two-resource-types-v1.0.0/README.md). It creates no new model or SIMLOX run.

The [frozen contract](contract.json) pins the published source and raw bytes of both radio arms, their accepted C05 capacity-two direct parent, and the A03/C01 prerequisites. Each aircraft requires one `MISSION-CREW` and one `MISSION-RADIO`. Crew capacity stays two; the pair changes only `ResourceAllocation.RQTY` for the radio from **2 to 0** and the description.

With radio capacity two, each aircraft passes both typed resource tests and books one crew and one radio at h7. The two-aircraft mission launches h8, succeeds h10, releases all four booked units, and finishes with both aircraft ready. With radio capacity zero, both crew tests pass and both radio tests fail. Neither resource type books for either aircraft; the mission never launches and cancels h8.33333. This is a **per-system** all-required-types observation. The separate C05.var01 capacity-one evidence shows that formation assignment can be partial, so this package makes no formation-level atomicity claim.

The read-only [author checker](check_reclassification.py) validates source identities, both original closures and 24 raw seals, the direct parent's 12 raw seals, exact 16 row-containing-table native roundtrip per arm, physical event ordering and the full six-table report grid of 5,210 cells per arm. Its deterministic [verdict](author-validation.json) passes **8,035/8,035**. The separately authored [independent replay](review/independent_replay.py) passes **14,180/14,180**; its [verdict](review/independent-verdict.json) and [postrun memo](review/independent-postrun-review-2026-10-07.md) confirm the bounded source claim. The evidence index seals these bytes before independent publication review.

The original source has one seed, a two-hour mission and two resource types. Radio capacity one, additional types, ground preparation, other seeds, GUI-only behavior, general scheduling rules and cross-engine equivalence remain unverified.
