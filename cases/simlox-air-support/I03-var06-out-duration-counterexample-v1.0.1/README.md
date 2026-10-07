# I03.var06 fixed OUT TFDT4 counterexample — evidence-only v1.0.1

Status: author read-only replay passes; independent postrun/content review and publication are pending. This package makes **zero native calls**. The single v1.0.0 prospective run and its behavior checker remain `NO_GO_RUN` with exit 1. The accepted comparator is published I03.var02 idle-crew OUT TFDT0.

The original v1.0.0 child input changed only PDESC and `ResourceTransfer.TFDT` from 0 to 4. Its sealed export retains TFDT4. At h6, the same quantity-one P-CREW OUT task starts and prints transfer time 4; it arrives at h10. The accepted TFDT0 parent prints time 0 and arrives at h6. No second local decrement or backorder appears. The in-transfer and completed-OUT quantities are derived from this linked task, not observations of a persistent outside person identity.

The direct author reader independently reconstructs each arm's 5,210 report cells from source, complete typed events, and the separately declared bounded native presentation fields. The original reports have 5,209 equal corresponding cells and one authored PDESC difference. On-station ResourceResultsTotal means are equal, including exact binary32 NR/NRA/NRN `1.1666666269302368`, NRUM `0.0555555559694767`, and NRW `0.02777777798473835`. Equal reports do not erase the h6–h10 transit difference.

The installed manual pp478–479 describes OUT TFDT as ignored; this one installed executable/source row prints duration 4 and links arrival at h10. This is a bounded counterexample to the prior expectation. It does not establish a general OUT algorithm, another SIMLOX version, IN/BETWEEN behavior, GUI, performance, or cross-engine equivalence.

`contract.json` and `MODEL-LINEAGE.md` are byte-identical approved contract-stage snapshots. `preserved-v100-source/` contains inert exact source/review copies; `preserved-root-context-v3/` contains small exact preflight/native/guard copies. Earlier incomplete copy drafts and partial copies remain under `preserved-development/` and historical directories as failed development evidence. The accepted/context 118 raw records and 26 failed-child run files remain mandatory at their original sealed paths. The old v1.0.0 reader, its KeyError stderr, original failed checker output and NO_GO memo are historical evidence and are never run as an acceptance method here.

See `REPRODUCTION.md` for read-only replay and custody steps. The central publication index is authoritative only after independent content, staged and remote review; no entry has yet been appended for this v1.0.1 classification.
