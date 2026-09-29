# Capability index

The [progressive catalog v2](progressive-catalog-v2.md) and [machine catalog](catalog-v2.json) are frozen planning snapshots: 108 cases, 579 named variants and 133 mapped input tables do not mean those scopes are published. The [publication index](publication-index-v1.json) lists **27 accepted bounded CLI packages covering 22 distinct case IDs** as of 2026-09-30. Each linked sign-off or evidence report defines the verified behavior and limits. Full manual-method coverage, GUI-specific behavior and cross-engine equivalence require their own evidence. The [manual coverage](manual-coverage-v2.json) and [findings](known-issues/manual-review-v2.md) retain the broader unverified methods and source conflicts.

| Need | Smallest accepted scope | Evidence and important limit |
| --- | --- | --- |
| One generic aircraft and one scheduled mission | [A01](A01-single-aircraft-single-mission/cli-scope-signoff-2026-09-29.md) | One bounded normal CLI mission and ready return. |
| Reuse one aircraft across three missions | [A02](A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md) | Three nonoverlapping waves and ready returns. |
| Two-aircraft formation | [A03](A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md) | One fixed two-aircraft mission. |
| Nested mission profile | [A09](A09-hierarchical-operation-profile-v1.0.1/cli-scope-signoff-2026-09-29.md) | One fixed four-wave recipe; general expansion rules remain unverified. |
| Two explicit units supplying a formation | [A17](A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md) | One aircraft from each unit; selection priority and transfer remain unverified. |
| Fixed and serial mission preparation | [B01](B01-fixed-preparation-v1.0.1/evidence-2026-09-29.md), [B02](B02-serial-preparation-v1.0.2/evidence-2026-09-29.md) | Fixed preparation and explicit ordered 10/20-minute work. |
| Different cold and hot preparation | [B03](B03-explicit-cold-hot-v1.0.2/evidence-2026-09-29.md) | Explicit mission types select the recipe; no automatic sortie-history switch. |
| Personnel and equipment capacity | [C01](C01-personnel-capacity-v1.0.2/evidence-2026-09-29.md), [C02](C02-joint-resources-v1.0.2/evidence-2026-09-29.md) | Specialty/quantity controls and one joint crew-device request. |
| Two aircraft sharing preparation crew | [C03](C03-shared-crew-formation-v1.0.2/evidence-2026-09-29.md) | Capacity two, one and zero in one fixed formation. |
| Fixed formation cutoff and cancellation cleanup | [C04](C04-deadline-cancellation-v1.0.0/evidence-2026-09-29.md) | Five accepted CLI runs; its short-horizon waiting probe failed and remains unpublished. |
| Random system failure and direct repair | [D01 system](D01-system-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) | One fixed seeded system-level repair slice. |
| Installed LRU failure, replacement and repair | [D01 LRU](D01-installed-lru-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) | One installed item, one local spare and repaired-item return. |
| Calendar preventive maintenance | [D03](D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md) | One fixed one-hour PM at 24–25 and 49–50 hours; conflict and resource behavior remain unverified. |
| Operation-hour preventive maintenance | [D04](D04-flight-hour-pm-v1.0.0/cli-scope-signoff-2026-09-30.md) | Two missions accumulate three `OPHOURS`; no PM during the 30-hour no-flight gap, then one PM after the second return. |
| One critical repair versus noncritical PM sharing a worker | [D05 bounded slice](D05-maintenance-competition-v1.0.0/cli-scope-signoff-2026-09-30.md) | One failure and five-hour direct repair hold the sole worker 23–28; two PM subtasks follow 28–29 and 29–30. Full D05 priority and capacity variants remain unverified. |
| Limit simultaneous noncritical PM work | [D13.var02](D13-var02-maxpm-two-v1.0.0/cli-scope-signoff-2026-09-30.md) | Two aircraft and fixed one-hour PM: `MAXPM=1` serializes actual subtasks, `MAXPM=2` runs them together; both task objects start at hour 24. |
| Local spare with physical REMOVE/REPLACE | [E01](E01-local-spare-explicit-replacement-v1.0.0/cli-scope-signoff-2026-09-29.md) | Ten-minute removal and twenty-minute replacement step. |
| Local zero-stock backorder | [E02](E02-zero-stock-local-backorder-v1.0.0/cli-scope-signoff-2026-09-29.md) | One backorder cleared by repair of the same failed item. |
| Two aircraft competing for one local spare | [E03](E03-two-aircraft-shared-spare-v1.0.0/cli-scope-signoff-2026-09-29.md) | One second-customer backorder; FIFO across multiple pending demands is unverified. |
| Stocked depot with two-hour transport | [E04 FAST](E04-upstream-transport-fast-v1.0.0/cli-scope-signoff-2026-09-29.md) | One FAST support link and bidirectional physical transport. |
| SLOW demand propagation | [E04.var01](E04-upstream-transport-slow-v1.0.0/cli-scope-signoff-2026-09-29.md) | One SLOW link; depot demand waits for the failed item to arrive. |
| Upstream stockout repaired and supplied back | [E04.var02](E04-upstream-shortage-v1.0.0/cli-scope-signoff-2026-09-30.md) | One propagated backorder at each station; repaired item bypasses depot stock. |
| Zero transport time | [E04.var03](E04-upstream-transport-zero-v1.0.0/cli-scope-signoff-2026-09-30.md) | One FAST link; zero-duration backorder event still occurs. |
| Spare unreceived at simulation stop | [E04.var04](E04-horizon-in-transit-v1.0.0/cli-scope-signoff-2026-09-30.md) | One 30-hour downward task pending at hour 36 by event-based inference; post-horizon arrival unobserved. |
| Local repaired item restocked and reissued | [E05](E05-local-repair-reissue-v1.0.0/cli-scope-signoff-2026-09-29.md) | Fixed seeded local loop with later reissue. |

Result collection end before/during/after a no-fault mission has separate A01 CLI probes: `SystemResults.FTMO` clips to the report window while the event log continues. A01 short-simulation-period probes near a crossing mission were rejected by native input check `#204`; their input-feasibility result does not establish generic crossing-stop behavior. [E04.var04](E04-horizon-in-transit-v1.0.0/cli-scope-signoff-2026-09-30.md) tests a shipment beyond the normal 36-hour stop, not a shortened mission horizon. Earlier PR #15's cancellation and PRU/SPRU probes remain separate from this library's case sign-offs. See [known issues](known-issues/README.md).
