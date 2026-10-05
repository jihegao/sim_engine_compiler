# I07.var07 — simultaneous depot ROSIZ change and OUT transfer

This fixed-seed matched pair tests the installed manual's same-time scheduled
change and item-transfer rule on one existing stock-based discardable DU at
`DEPOT-01`. It derives from accepted E15 explicit initial on-hand three,
nominal stock four and ROSIZ two. Both arms schedule the same one-unit OUT
transfer at hour 5. Only the child also changes ROSIZ from two to one at
hour 5. The accepted I07.var02 isolated ROSIZ change and I02 OUT syntax are
byte-pinned prerequisites and were not rerun.

Both arms issue physical ID0 at hour 5, reducing nominal stock from four to
three and depot on-hand from three to two. The control has no hour 5 order.
The changed arm starts an hour 5 reorder after the stock issue and receives
one new physical item, ID4, at hour 6. The ordinary hour 10 demand moves
physical ID1 from depot to base in both arms, reaching base at hour 12.
The control then orders two items at hour 10 and receives IDs5/6 at hour 11;
the child orders one and receives ID6 at hour 11. These batch quantities
come from native events; the first batch was not assumed to equal ROSIZ.
The physical IDs of subsequently installed failed items differ because the
child's earlier order creates an extra item.

The guarded session-0 SSH run sealed 24 raw files. Both arms passed exact
23-table pre-calculation roundtrip and conversion Errors0/Warnings1 (sole
warning #108)/Notes0. The protected GUI PID13340 in session1 was preserved.
The author replay verifies each stock event, all 72 selected depot half-hour
STSZ/STOHA/NRO/NBO bins per arm and unchanged mission, system, summary and
aggregate stock results. Its outcome and an independent read-only review are
under `review/`. Raw SXI/SXO, logs and selected reports remain in ignored
`runs/` and are pinned by `evidence-index.json`.

The result supports the manual's same-time rule for this frozen available
stock, zero-delay transfer. It does not establish a general native event
priority rule, unavailable-stock or nonzero-duration transfer behavior,
other stock policies, GUI behavior, cross-engine equivalence, full I07 or
overall Issue #18 completion.
