# G10.var02: zero-delay PASSIVE 1-of-2 links

This bounded candidate derives from accepted [G10.var01](../G10-var01-active-single-link-v1.0.0/cli-scope-signoff-2026-10-03.md). Only the redundancy's `ACPA` changes from ACTIVE to PASSIVE, plus descriptive text; `TSWOV` remains zero. The [contract](contract.json) and [input](native-input.json) are frozen before the guarded native run.

Run `build.py` to verify parent/input bytes, `describe_diff.py` for the exact two-table delta and `validate_native.py runs/g10-var02-passive-zero-v100-ssh-20261003-01` for the author replay. The separate [review checker](review/independent_readonly.py) does not import author validation. The session-0 SSH runner preserves GUI PID 13340 and the host-wide native mutex. Raw results remain under ignored `runs/`; the [signoff](cli-scope-signoff-2026-10-03.md) states the bounded behavior and the [evidence index](evidence-index.json) records local raw hashes.
