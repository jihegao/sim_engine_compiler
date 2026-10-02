# I02.var01 — scheduled IN transfer to depot

This bounded case extends the accepted E04 FAST upstream-transport model. One
`ItemTransfer` row moves one `TEACH-LRU-01` from `<OUTSIDE>` to `DEPOT-01` at
hour 4 with zero transfer duration. The initial depot nominal stock is one.
`Item.TRACK=Y` and half-hour `ITEM` result collection permit direct observation
of nominal stock (`STSZ`) and stock on hand (`STOHA`).

The frozen source differs from E04 only in that transfer row, the two result
collection controls, and the description. The source and exact table delta are
in `native-input.json`, `contract.json`, and `exact-diff.json`. `build.py` and
`describe_diff.py` reproduce them; `check_roundtrip.py` checks all 22 populated
authored tables after SIMLOX import/export.

`run_native_ssh.ps1` executes the pinned native model in the protected
session-0 SSH queue. `make_report_settings.py` recreates a local proprietary
`.sxs` selector from a fingerprinted installed default; the `.sxs` file is
ignored by Git. `probe_item_report_results_ssh.ps1` exports item-position
tables from the sealed SXO without recalculating the simulation. The two run
directories and all native raw files are local, ignored by Git, and SHA-256
sealed in `evidence-index.json`. `validate.py` and
`review/independent_readonly.py` replay the evidence without running SIMLOX.

The accepted observation is one `IN` transfer at one depot and seed: depot
`STSZ` and `STOHA` change from 1 to 2 at hour 4. A later ordinary demand at
hour 10 lowers on-hand stock while nominal stock stays 2; depot repair restores
on-hand stock after hour 13. No OUT or BETWEEN behavior, nonzero transfer
delay, shortage priority, reorder, procurement, GUI visual result, or
cross-engine parity is established by this case.
