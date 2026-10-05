# E14.var05 v1.0.0: excluded import-erasure hypothesis

**Decision: NO-GO for this frozen import-negative contract.** The accepted E14 seed-2 extra arm was changed in exactly one cell: `ItemStructure` record 2 `TEACH-SRU-01` `NFFF=2` became `5`, while `RRF=4` stayed fixed. The installed manual physical page 250, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, requires explicit `NFFF<=RRF`. Import-stage rejection was a hypothesis, based in part on the separate E14.var04 zero-value diagnostic.

Guarded session-0 SSH run `e14-var05-nfff-over-rrf-v100-ssh-20261005-01` completed native import/export with exit code zero and preserved GUI PID 13340/session 1. The importer issued **no** `cannot be imported` diagnostic. All 21 authored row-containing tables roundtripped exactly; the target row retained `NFFF=5,RRF=4`. The frozen checker expected erasure of only that cell, so it failed and the runner stopped before calculation. There is no converter log, valid SXO, simulation event or report for v1.0.0.

The immutable native closure SHA-256 is `2bc063c6dc8c1d318266ea55b1bcdc7147139cee35c9400d75414bf79a546ede`. The [evidence index](evidence-index.json), SHA-256 `c666a2d59eb830604890a79575fd6b52017b4297d58123971b49439c781aebd6`, seals eight ignored local raw files, source bytes and invocation. Source hashes were unchanged before and after. Independent review verified all seals and the exact roundtrip and classified this version excluded. The accepted E14 parent was not rerun.

This version establishes only import retention for one `NFFF=5,RRF=4` row. A separately frozen calc-only v1.0.1 experiment uses the byte-pinned SXI from this run. The failed v1.0.0 hypothesis is not retrospectively relabeled as a pass.
