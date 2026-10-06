# C05.var01: mission crew capacity 2/1/0

This is a read-only catalog classification of the already accepted [C05 mission-resource panel](../C05-mission-resource-v1.0.0/README.md). It reuses that package's three original guarded native runs. No new model or SIMLOX run was made.

The [frozen contract](contract.json) pins the accepted C05 source files and local raw closures, plus the A03 formation and C01 resource prerequisites. The pairwise source delta is only `ProblemDescription` and `ResourceAllocation.RQTY` for `AIR_BASIC`/`MISSION-CREW`/`BASE-01`: **2, 1, 0**. Every aircraft needs one `MISSION-CREW` for the mission.

The capacity-two run books both crew units at h7, launches two aircraft at h8, succeeds at h10, releases both units, and ends ready two. Capacity one books and assigns aircraft ID0 while ID1 fails its crew test; the mission never starts and cancels at h8.33333, releasing ID0's reservation. Capacity zero books neither aircraft and cancels at h8.33333. Thus the original pre-run all-or-none formation-assignment hypothesis was false.

The [author replay](check_reclassification.py) is read-only and passes **15,059/15,059** checks; its deterministic [verdict](author-validation.json) is preserved. The separate [independent replay](review/independent_replay.py) passes **21,056/21,056** and has its own [verdict](review/independent-verdict.json) and [postrun memo](review/independent-postrun-review-2026-10-07.md). Both check original source identity, three closures and 36 raw seals, physical event and resource ledgers, and the complete six-table reports of 5,210 cells per arm. The [signoff](cli-scope-signoff-2026-10-07.md) gives the precise accepted scope.

The teaching source has a two-hour mission at one seed, not the catalog's one-hour example. This reclassification adds no native behavior, general capacity law, GUI observation, or cross-engine validation. [make_evidence_index.py](make_evidence_index.py) is gated on the exact contract, independent reviews, and author result; independent publication review follows index creation.
