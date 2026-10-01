# E07 v1.0.0: excluded source-schema diagnostic

This candidate is **not published**. Its guarded native run `e07-item-route-v100-20261001-01` completed import, export, calculation and report export with zero converter errors, but the required exact input/export roundtrip failed. Native JSON export added nullable `ItemStationStructure.CFRMS` and `CTOMS` columns that the authored table omitted. All other 21 populated tables matched.

The original run remains in ignored `runs/`; [the diagnostic evidence index](diagnostic-evidence-index.json) SHA-256 `09f9bc7bc5a252c7bd3797f31fcd454499ab9677ccf441aaf297f62cc7a7f30a` records its raw byte lengths and hashes. No behavior is accepted from this candidate. [E07 v1.0.1](../E07-item-specific-transport-v1.0.1/README.md) adds the two native-export columns and uses a fresh immutable run.
