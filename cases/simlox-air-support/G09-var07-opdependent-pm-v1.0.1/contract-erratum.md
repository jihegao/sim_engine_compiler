# Frozen contract provenance correction

The frozen [contract](contract.json) `accepted_pm_pattern.reuse` text says D10.var02 supplied a system `MaterielPM` `OPHOURS` row. That wording is inaccurate. The pinned D10.var02 `native-input.json` has a base `MaterielPM` row `MS2/MISSIONS=2` and a separate `MaterielPMInterval` row `MS2/OPHOURS=3` (plus `CALHOURS=24`). It supplies a validated system PM task/location schema and a native operation-hour interval precedent. G09.var07 authors its own base `MaterielPM` row `SYS-OP15/OPHOURS=1.5`; it does not copy an identical D10 row.

The contract bytes remain frozen because both accepted v1.0.1 native closures pin their SHA-256. This correction changes neither the two model inputs nor the predeclared PM timing gate. The exact G09 table rows are verified by the [exact diff](exact-diff.json), 30-table native roundtrips, [author replay](author-validation.json), and independent review.
