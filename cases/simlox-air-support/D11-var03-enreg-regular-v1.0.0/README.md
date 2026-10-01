# D11.var03: delayed calendar PM, original schedule retained

This bounded CLI case changes only `MaterielPM.ENREG` from N to Y, plus a label, in the [short-delay control](../D11-var03-enreg-drift-v1.0.0/README.md). The mission spanning hour 24 delays first `CAL24` PM work to 25.5–26.5 in both runs. With `ENREG=Y`, the next PM works at the original hour-48 grid slot, 48–49, versus 50.5–51.5 with `ENREG=N`.

The [frozen contract](contract.json), [input](native-input.json), [exact control diff](exact-diff.json), [scope signoff](cli-scope-signoff-2026-10-01.md) and [evidence index](evidence-index.json) bind source and native output. `build.py` and `describe_diff.py` replay source construction. `validate_native.py runs/d11-enreg-regular-v100-ssh-20261001-01` and `review/independent_readonly.py` replay raw evidence separately. The session-0 SSH runner is `run_native_ssh.ps1`; original SXI/SXO, event log and report remain local under ignored `runs/`.
