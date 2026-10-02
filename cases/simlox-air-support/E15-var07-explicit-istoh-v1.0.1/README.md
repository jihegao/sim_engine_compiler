# E15 initial physical stock at a stock-based reorder position

This bounded case compares two source-bound DU models with the accepted G01.var03
discard/reorder run as direct behavioral donor. The catalog E02 prerequisite is
also accepted and pinned in `contract.json`. Both models use depot `STSIZ=4`,
`ROSIZ=2` and fixed one-hour `LEADT`; both set `Item.TRACK=Y` so the native
selected report includes the station-specific item-position series. Only the
depot's initial on-hand stock differs: omitted `ISTOH` (default 4) versus
explicit `ISTOH=3`.

The frozen contract used `E15.var07` as a work label. The catalog's full
E15.var07 boundary asks for explicit initial stock above nominal; this pair
tests 3 below nominal 4 (and above reorder point 2). It does not complete
the catalog variant.

The frozen contract predicted one ordinary h10 depot issue in each arm. The
accepted native runs show no reorder in the default arm and one two-unit
reorder at h10 delivered h11 in the explicit arm. The selected depot report
has 72 bins: nominal stock stays four in both; on-hand is 4→3 in the default
arm and 3→2→4 in the explicit arm. One mission aborts, two succeed, and the
aircraft is ready at the terminal horizon in both arms.

The prior v1.0.0 pair produced the predicted event contrast, but its selected
report lacked `ItemResults` because donor `Item.TRACK` was unset. Those runs
remain diagnostic and are excluded from this acceptance. The accepted v1.0.1
pair has four sealed local runs and 28 raw file seals. Author replay passes
242/242 and independent read-only replay passes 1,598/1,598. See
`cli-scope-signoff-2026-10-02.md` and `evidence-index.json` for the precise
scope, hashes and limits. This one demand does not close full E15 or Issue #18.

`build.py` regenerates both frozen inputs from the accepted donor; without
`--write`, it checks byte identity. Native raw files stay under ignored `runs/`.
