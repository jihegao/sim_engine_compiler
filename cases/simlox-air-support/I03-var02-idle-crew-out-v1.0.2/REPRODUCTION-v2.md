# I03.var02 v1.0.2 corrected prelaunch snapshot

The child is prospective and has not run. The frozen contract predicts one idle P-CREW OUT at h6, followed by serial aircraft preparation in two waves. The accepted I03.var01 busy OUT run remains a read-only comparator. The earlier author event gate, independent v1 method and `prelaunch-manifest.json` are preserved as rejected preflight drafts; none authorized native execution.

From the repository root, use the bundled Python for read-only checks:

```powershell
$py = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$case = 'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
& $py -X utf8 -B "$case/build.py"
& $py -X utf8 -B "$case/verify_sources.py" --mode live --manifest "$case/prelaunch-manifest-v2.json"
& $py -X utf8 -B "$case/test_sealed_catalog.py"
& $py -X utf8 -B "$case/self_check.py"
& $py -X utf8 -B "$case/make_prelaunch_manifest_v2.py"
```

The source verifier requires 20 accepted local/Git source pairs, 34 original parent run records, three installed byte identities, and exact archived history. The archived selection catalog and base Git bytes are distinct. A later sealed replay allows an append to the live catalog only when the first 490 entries and non-entry metadata remain unchanged. An absent accepted parent raw file is a missing dependency; it must not be regenerated.

The receipt tests exercise production validation without native work:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$case/test_preflight_receipt.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$case/test_checker_receipt.ps1"
```

The new author event gate binds typed return checks to their subtasks, free-resource continuations to the live quantity ledger, and ready increases to opening and completed mission edges. Its synthetic fixture reconciles 5,210 expected report cells and rejects 33 semantic mutations. The independent final method is a separate implementation. These static results are not a child native result.

After exact-file independent static approval, root alone may invoke the final manifest-pinned `run_native_ssh_v3.ps1 -PreflightOnly` under actual SSH PowerShell 5. That mode creates no native child or run directory. A separate GO_PRELAUNCH must bind the resulting receipt, manifest, runner, validator, input and independent method before root may run the unique child. The runner waits for each child and records actual PID, session, integer OS exit, stdout and stderr; it does not kill or interrupt a process.

Any pin, event, quantity, report-cell, exact binary32 mean, GUI identity or approval failure is NO_GO. Preserve raw output and failure seals. A changed input or claim requires a new version and review. This case does not establish GUI, performance, cross-engine or general I03 behavior.
