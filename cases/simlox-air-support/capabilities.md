# Capability index

| Mechanism | Smallest case | Native evidence | Reuse state |
| --- | --- | --- | --- |
| One generic aircraft, one scheduled mission, no support | A01 | Final native run and fresh replay: one launch/completion, 2 h FTMO integral, NPSTA=0; GUI pending | CLI behavior verified; publication provisional |
| Same aircraft reused for three non-overlapping scheduled missions | A02 | Final native run and fresh replay: three matching mission identities and ready returns, 6 h FTMO integral; GUI pending | CLI behavior verified; publication provisional |
| Result collection end before/during/at/after mission | A01 collection probes | Five valid CLI probes: `SystemResults.FTMO` interval integral clips to collection end while full ENLOG continues to 10 h | CLI output mapping verified for one no-fault mission |
| Simulation period end near scheduled mission | A01 SIMPE probes | Five early models rejected by `#204` with 4-byte SXO; 10.5/12 h positive controls valid | Input feasibility bounded for this model; crossing-stop behavior unverified |
| Preparation, resources, fault, PM, stock and transport | A03–F04 as specified in catalog | No case-library validation in this slice | Planned |

Prior PR #15 contains independent SIMLOX 2017 mechanism evidence: 20 cancellation probes and six PRU/SPRU shared-spare probes. Those probes are **not** A01/A02 acceptance, and their J35 wave-20 and nested-LRU gaps remain open. See [known issues](known-issues/README.md).
