# I03.var02 v1.0.2 prelaunch reproduction snapshot

This package is prospective. The v1.0.2 child has not run. The immutable contract predicts one idle P-CREW OUT at h6 and serial aircraft preparations in two waves. The accepted I03.var01 busy OUT run is read only and remains the comparator. Its accepted source and raw byte identities, plus the excluded v1.0.0/v1.0.1 contract attempts, are pinned in `contract.json`.

Using the bundled Python from the repository root, the static author checks are:

```powershell
$py = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$case = 'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
& $py -X utf8 -B "$case/build.py"
& $py -X utf8 -B "$case/verify_sources.py" --mode live
& $py -X utf8 -B "$case/self_check.py"
& $py -X utf8 -B "$case/make_prelaunch_manifest.py"
```

The builder is read only by default and requires the already frozen input and diff. The verifier requires the 20 accepted disk/Git source pairs, 34 accepted parent run records, three installed byte identities and 26 historical inert copies. It checks the historical catalog archive and distinct base Git blob. Before native work, the live catalog must still match the selection-time bytes; a later sealed replay compares its original 490 entries and all non-entry metadata and permits only appended entries. A missing accepted raw file is a missing dependency, not a reason to regenerate it.

The PowerShell receipt tests invoke production receipt validation without a native child:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$case/test_preflight_receipt.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$case/test_checker_receipt.ps1"
```

After independent exact-file static approval, root alone will use actual SSH PowerShell 5 with `run_native_ssh.ps1 -PreflightOnly`. That mode checks the protected GUI, WTS session, mutex, source bytes and unique absent run path, then writes a separate receipt under `review/` without creating a run directory or native child. Native execution requires a later independent GO_PRELAUNCH bound to that receipt and the exact manifest. The runner waits for each child and records actual PID, session, integer OS exit, stdout and stderr; it never terminates a native or GUI process.

If a pin, parser, typed resource conservation, half-hour cell, exact binary32 total, approval or GUI identity fails, the prospective gate is NO_GO. Preserve any resulting run and failure seal. A changed input or claim requires a new version, unique run ID and independent review; the accepted parent is not rerun. This snapshot does not claim GUI, performance, cross-engine or general I03 behavior.
