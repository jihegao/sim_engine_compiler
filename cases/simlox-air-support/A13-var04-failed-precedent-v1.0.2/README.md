# A13.var04 failed START precedent

This package compares a failed fixed RECON precedent with and without one FOLLOW START dependency. Read the [CLI scope sign-off](cli-scope-signoff-2026-10-01.md) for the accepted native observation and limits. The [contract](contract.json), [builder](build.py), [exact diff](exact-diff.json), two source inputs, guarded [SSH runner](run_native_ssh.ps1), and [author replay](validate.py) support a source-bound reconstruction. The independent review is under `review/`.

The v1.0.0 source was rejected before native execution because its inherited 25% success point could precede the planned failure. The v1.0.1 control run produced the target native failure and a complete report, but its runner stopped at an incorrect populated-table count; that sealed run remains an excluded diagnostic. v1.0.2 retains the corrected v1.0.1 inputs and uses a fixed checker with fresh immutable run IDs. Raw native artifacts are held in ignored local `runs/`, with SHA-256 closures and selected hashes in the sign-off and review report.

Rebuild the two inputs with `python build.py`, regenerate the table diff with `python describe_diff.py`, and replay the sealed native result with `python validate.py` and the independent read-only reviewer. A new native run requires a new ID and the pinned session-0 SSH environment.
