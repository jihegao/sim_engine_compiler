# G09.var03 v1.0.2 excluded two-copy diagnostic

Both arms derive from the accepted omitted POS-B noncritical-set arm and physically install two POS-B copies. The only paired business delta is `RBDNonCriticalSetItems.QTYNC` 1 versus 2; descriptions also differ. The frozen schedule retained PAR-MISSION at h20. The [exact diff](exact-diff.json) and [contract](contract.json) record the source and hypothesis.

Two guarded session-0 SSH runs converted with zero errors and reviewed warning #108. Both roundtripped all 27 populated tables. Matched POS-B faults occurred at h8.37658, h20.4933 and h21.742 in both. The first h20 fault was noncritical and the second critical in both; PAR aborted at h21.742 in both. The selected PAR mode uses the active parallel RBD, so this run does not demonstrate a QTYNC1/QTYNC2 BASIC-mode distinction. The native log does not print NCID, QTYNC or separate physical copy IDs.

The frozen positive distinction was unobserved. These runs are [sealed as an excluded diagnostic](diagnostic-evidence.json), not counted in the publication index. The revised [v1.0.3 BASIC pair](../G09-var03-nc-quantity-v1.0.3/README.md) tests two h20 POS-B faults while the selected BASIC NCID applies.
