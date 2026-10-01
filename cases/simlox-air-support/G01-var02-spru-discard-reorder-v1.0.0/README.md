# G01.var02: secondary SPRU repair and discard/reorder paths

This bounded CLI package derives from the accepted [G01.var03 nested DP topology](../G01-var03-dp-discard-reorder-v1.0.0/cli-scope-signoff-2026-10-01.md). Its [seed-1 companion](../G01-var02-spru-partial-repair-v1.0.0/README.md) differs only in `Control.RSEED`. Seed 7 observes a repaired SPRU, a distinct discarded SPRU with a one-unit depot reorder, and a later SPRU still under repair at the 36-hour horizon. These observations do not establish a 50/50 frequency law.

The [pre-run contract](contract.json), [native input](native-input.json), [exact parent diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md), and [evidence index](evidence-index.json) define the accepted scope. Run `build.py` and `describe_diff.py` to check source bytes and table delta, `validate_native.py runs/g01-var02-spru-discard-v100-ssh-20261001-01` for author replay, and `review/independent_readonly.py` for separate paired raw replay. Original SXI/SXO, event log, report, invocation and closure stay local under ignored `runs/g01-var02-spru-discard-v100-ssh-20261001-01/`.

Seed-specific `v0.1.0` runs for seeds 2–7 were diagnostic and remain untracked and unpublished. The first observed discard in seed 7 informed this final pre-run contract. This package uses a fresh path and run ID for acceptance.
