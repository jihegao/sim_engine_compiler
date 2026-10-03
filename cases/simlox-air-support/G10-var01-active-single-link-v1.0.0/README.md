# G10.var01: active 1-of-2 single-item links

This bounded candidate derives from accepted [G01.var05](../G01-var05-qty-two-v1.0.0/cli-scope-signoff-2026-10-01.md). The [contract](contract.json) and [input](native-input.json) are frozen before native execution. The manual supports single-item redundancy links by using the item IID as RLID, so this variant has one `Redundancy` row and no `RedundancyLink` row.

Run `build.py` to verify parent and input bytes and `describe_diff.py` to verify the three-table delta. `validate_native.py runs/g10-var01-active-v100-ssh-20261003-01` replays the author checks. The separate [review checker](review/independent_readonly.py) reads the source and sealed native artifacts without importing the author implementation. [Signoff](cli-scope-signoff-2026-10-03.md) states what the fixed-seed run proves. Native execution uses the session-0 SSH runner, host-wide mutex and preserved GUI PID 13340. Raw SXI/SXO, logs, report, invocation and closure remain under ignored `runs/`; the [evidence index](evidence-index.json) lists their local hashes.

Only ACTIVE 1-of-2 single-item redundancy with this fixed seed is in scope. Series links and PASSIVE switching are planned separately.
