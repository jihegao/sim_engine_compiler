# K07: source-bound CLI lifecycle and result classification

This bounded package exercises K07.var02, K07.var03 and one K07.var05 diagnostic on the accepted K02.var01 teaching input. The [contract](contract.json) freezes the parent, input hashes, native commands, and limits. `build.py` verifies that `normal-input.json` is byte-identical to K02 and that `inactive-base-input.json` adds only `Station` instance `K02-BASE` `inactive_rows=[1]`.

The guarded [runner](run_native_ssh.ps1) uses an immutable run directory, session-0 SSH with `sshd.exe` ancestry, `Global\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 checks, and a 60-second watchdog for its own native children. The positive arm imports/exports/calculates/reports with `-silent`; `-convert` acts only on a copy of the freshly imported SXI, followed by JSON export. The negative arm imports/exports/calculates a source with the active teaching station disabled. All nine CLI steps exited zero, but native conversion of that negative arm reported four errors and generated only a four-byte SXO. Process exit zero is therefore not a successful simulation gate.

Run ID: `k07-var02-cli-evidence-v100-ssh-20261004-01`. The [evidence index](evidence-index.json) lists the closure SHA-256 and 23 task-local raw artifact IDs, sizes, and hashes. Raw files are retained under ignored `runs/`. The [sign-off](cli-scope-signoff-2026-10-04.md) gives the accepted observation, exact diagnostics, and remaining limits.

Read-only author replay:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\cases\simlox-air-support\K07-var02-cli-evidence-v1.0.0\validate_native.py
```

The installed manual documents a separate `Tools::Test` GUI command on physical page 110. This CLI run did not invoke it. It also does not demonstrate old-format conversion, thread-count reproducibility, arbitrary diagnostic classification, or full K07.
