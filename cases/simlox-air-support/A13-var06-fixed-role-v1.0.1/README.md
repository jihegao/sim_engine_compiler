# A13.var06 START dependency role matrix

This package tests which mission role must be FIXED for one explicit START dependency. Read the [CLI scope sign-off](cli-scope-signoff-2026-10-01.md) for the accepted observation and its limits. The frozen [contract](contract.json), five source inputs, [exact diff](exact-diff.json), [builder](build.py), guarded [native runner](run_native_ssh.ps1), [author replay](validate.py), and [independent read-only replay](review/independent_readonly.py) make the decision reproducible.

The earlier v1.0.0 static candidate retained travel fractions on CONTINUOUS mission roles. An independent pre-run check found the known converter incompatibility, so v1.0.0 was not run natively and is not published. This corrected v1.0.1 clears those fractions in the CONTINUOUS-role inputs and uses a valid matched no-dependency control for each role.

The five immutable native runs are preserved locally under ignored `runs/`. Their closure fingerprints and selected raw-file hashes are in the sign-off and the independent report; rerunning requires new run IDs and the pinned host environment. Rebuild inputs with `python build.py`, inspect the exact delta with `python describe_diff.py`, and replay evidence with `python validate.py` and `python review/independent_readonly.py`.
