# A13.var04 premature-stop converter limit

The [CLI scope sign-off](cli-scope-signoff-2026-10-01.md) accepts only the paired native `Operations` #204 conversion rejection for this hour-11 stop. It does not establish runtime behavior of an unfinished predecessor. The [contract](contract.json), [builder](build.py), [exact diff](exact-diff.json), paired source inputs, guarded [runner](run_native_ssh.ps1), [author replay](validate.py) and [independent replay](review/independent_readonly.py) document that narrow decision. Sealed raw artifacts remain in ignored local `runs/`.

v1.0.0 was excluded before native execution because its explicit result windows still ended at 24. v1.0.1 corrected the source but failed its planned behavior gate with #204; those two runs are retained as diagnostics. v1.0.2 retains the v1.0.1 inputs byte for byte, freezes a converter-level gate, and uses fresh paired runs.
