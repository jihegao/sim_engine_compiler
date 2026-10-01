# G01.var02: primary PRU repair branch

This bounded CLI package derives from the accepted [G01.var03 primary DU topology](../G01-var03-du-discard-reorder-v1.0.0/cli-scope-signoff-2026-10-01.md). The matching [discard/reorder branch](../G01-var02-pru-discard-reorder-v1.0.0/README.md) changes only `Control.RSEED` from 1 to 2. Together they observe both outcomes under one PRU repair/discard policy; two seeds do not establish a 50/50 frequency law.

The [pre-run contract](contract.json), [native input](native-input.json), [parent diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md), and [evidence index](evidence-index.json) define the accepted scope. Run `build.py` and `describe_diff.py` to verify source identity, `validate_native.py runs/g01-var02-pru-v100-ssh-20261001-02` for author replay, and `review/independent_readonly.py` for separate paired read-only replay. The original SXI/SXO, event log, report, invocation and closure remain local under ignored `runs/g01-var02-pru-v100-ssh-20261001-02/`.

The first `-01` run is preserved locally as an unpublished diagnostic: the copied round-trip checker expected 21 populated tables although this PRU input has 22. Its native stages executed, but the fifth checker stage failed. The checker was corrected before the successful fresh `-02` run, without changing the frozen input or contract.
