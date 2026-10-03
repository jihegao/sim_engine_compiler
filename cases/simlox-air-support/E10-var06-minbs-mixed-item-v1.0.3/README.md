# E10.var06 mixed-item MINBS pair, v1.0.3

This bounded case extends the [accepted same-item MINBS pair](../E10-var06-minbs-same-item-v1.0.0/README.md) with a second replaceable LRU type. It tests whether `MINBS=2` can put **different** item types on one physical depot-to-base transport when both use the same general transport data. It is a fixed-seed structural replication, not a transport-time or readiness improvement claim.

## Frozen inputs and provenance

Both arms derive directly from the accepted E10.var06 same-item inputs. They clone `TEACH-LRU-01` into `TEACH-LRU-02` in `Item`, `ItemStructure`, `ItemRepair` and the base/depot `StockAllocation` rows. `System.FRT` rises from 3,000,000 to 6,000,000 to satisfy the installed manual's mother–child failure-rate rule (physical PDF p. 255). `Control.RSEED` changes from `1` to `2`, and `ProblemDescription` states the variant. The arms differ only in `ProblemDescription` and ONDEM `TransportPolicyProfile.MINBS` 1 versus 2. No additional transport-data row is authored. See the [pre-run contract](contract.json), [exact diff](exact-diff.json), and frozen [MINBS1](native-input-minbs1.json) and [MINBS2](native-input-minbs2.json) inputs.

Three earlier immutable diagnostics are disclosed in the contract and retained locally: v1.0.0 seed 1 yielded only same-IID demands; v1.0.1 seed 2 yielded two mixed-IID demand pairs but exceeded its exactly-two-demand gate; v1.0.2 reduced the mission count to one and yielded only one depot demand. They are not published as accepted cases. This v1.0.3 package repeats the v1.0.1 frozen inputs under a separately declared **exactly-four-demand, two mixed-pair** contract and fresh guarded native runs. It is a reproducibility demonstration of a known fixed-seed effect.

## Acceptance boundary

The four depot spare demands must occur as two pairs, one each of `TEACH-LRU-01` and `TEACH-LRU-02` per pair. MINBS1 must send four separate one-item downward tasks. MINBS2 must cancel or hold a provisional first task for each pair, then send one two-item physical downward task per pair, each with both item IDs. The source, raw SHA seals, import/export of all authored populated tables, zero conversion errors, two-hour arrivals, upward failed-item cycles, inventory/backorders, mission outcomes, all 72 half-hour report bins, and terminal state must reconcile. Independent read-only review is required before publication.

The claim is restricted to two LRU types, one general depot-to-base link, one seed, `MINBS=1/2`, and simultaneous mixed demand pairs. Mixed system shipments, separate item-specific transport data, larger thresholds, partial batches at the end of the horizon, GUI visuals, cross-engine parity, and full E10/E11 completion remain open.

The bulky native raw files remain under ignored `runs/`; the evidence index records their local paths, byte lengths and SHA-256 values. Run `validate_native.py` from this package to replay the author's bounded check. The separate `review/` checker independently reads the frozen source and raw artifacts.
