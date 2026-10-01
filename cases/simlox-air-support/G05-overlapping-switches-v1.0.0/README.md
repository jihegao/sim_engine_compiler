# G05 overlap duration diagnostic (not published)

This frozen diagnostic pair adds nonfailing POS-D to the accepted G05 two-operated, NBREQ=2 parent. The paired inputs differ only in `RBDParallel.TSWOV`: 0.5 versus 4 hours, plus description. Both guarded session-0 SSH runs completed with zero converter errors and exact 23 populated-table roundtrips.

The short arm switches B→C h8.62763–9.12763 and A→D h11.5942–12.0942. The four-hour arm switches B→C h8.62763–12.6276 and A→D h15.0942–19.0942. **Neither pair overlaps.** The four-hour arm's second failure moves later with switch completion; its system report integrates 8 hours of `NSYSW` and 18 hours of operation. Both missions succeed and finish direct CM. This input does not meet the `G05.var05` positive gate and has no publication-index entry.

The native log at first B failure initially names h16.7498 as the next random failure. A longer switch is tested separately in [`v1.0.1`](../G05-overlapping-switches-v1.0.1/README.md), with its own frozen inputs and new run IDs. See [diagnostic result](diagnostic-result.json) for run and raw hashes. The ignored `runs/` directories retain the original bytes.
