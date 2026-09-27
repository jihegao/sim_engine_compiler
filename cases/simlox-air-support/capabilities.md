# Capability index

The [v2 progressive catalog](progressive-catalog-v2.md) covers the installed SIMLOX 2017 manual's method families and 133 input tables with acceptance plans. Its 108 cases and 579 variants are planning coverage. The native evidence below retains its original scope; no new case was simulated for the manual review. The [coverage index](manual-coverage-v2.json) marks every full method scope as unverified, and [manual findings](known-issues/manual-review-v2.md) identify restrictions and unresolved source conflicts.

| Mechanism | Smallest case | Native evidence | Reuse state |
| --- | --- | --- | --- |
| One generic aircraft, one scheduled mission, no support | A01 | Final native run and fresh replay: one launch/completion, 2 h FTMO integral, NPSTA=0; GUI pending | CLI behavior verified; publication provisional |
| Same aircraft reused for three non-overlapping scheduled missions | A02 | Final native run and fresh replay: three matching mission identities and ready returns, 6 h FTMO integral; GUI pending | CLI behavior verified; publication provisional |
| Result collection end before/during/at/after mission | A01 collection probes | Five valid CLI probes: `SystemResults.FTMO` interval integral clips to collection end while full ENLOG continues to 10 h | CLI output mapping verified for one no-fault mission |
| Simulation period end near scheduled mission | A01 SIMPE probes | Five early models rejected by `#204` with 4-byte SXO; 10.5/12 h positive controls valid | Input feasibility bounded for this model; crossing-stop behavior unverified |
| Remaining business mechanisms, structures, damage, transfers, experiments and authoring workflows | See catalog v2 A–K | No additional case-library behavior validation from this review | Planned |

Prior PR #15 contains independent SIMLOX 2017 mechanism evidence: 20 cancellation probes and six PRU/SPRU shared-spare probes. Those probes are **not** A01/A02 acceptance, and their J35 wave-20 and nested-LRU gaps remain open. See [known issues](known-issues/README.md).
