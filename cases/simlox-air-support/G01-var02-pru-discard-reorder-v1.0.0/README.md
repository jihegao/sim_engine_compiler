# G01.var02: primary PRU discard and reorder branch

This bounded CLI package derives from the accepted [G01.var03 primary DU topology](../G01-var03-du-discard-reorder-v1.0.0/cli-scope-signoff-2026-10-01.md). The matching [repair branch](../G01-var02-pru-partial-repair-v1.0.0/README.md) has the same business tables and PRU policy; only `Control.RSEED` changes from 1 to 2. Together they observe both outcomes, not a statistical 50/50 law.

The [pre-run contract](contract.json), [native input](native-input.json), [parent diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md), and [evidence index](evidence-index.json) define the accepted scope. Run `build.py` and `describe_diff.py` to verify source identity, `validate_native.py runs/g01-var02-pru-discard-v100-ssh-20261001-01` for author replay, and `review/independent_readonly.py` for separate paired read-only replay. The original SXI/SXO, event log, report, invocation and closure remain local under ignored `runs/g01-var02-pru-discard-v100-ssh-20261001-01/`.

An earlier seed-2 `v0.1.0` diagnostic run is preserved locally and excluded from publication. Its observed discard path informed this package's frozen contract; the accepted run used a fresh path and ID. A second PRU begins depot repair near hour 36 and remains unfinished at the horizon.
