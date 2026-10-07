# C02.var01 v1.0.1 prelaunch reproduction

This is a frozen prospective child design. No C02.var01 native result is accepted by this document. The only new source is `native-input.json`; `build.py` verifies that it differs from the sealed C02 single-both input only in ProblemDescription.PDESC and P-CREW ResourceAllocation.RQTY 1→0. The original parent is never rerun.

From the repository root, use the bundled Python without bytecode writes:

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pkg = 'cases/simlox-air-support/C02-var01-personnel-zero-v1.0.1'
& $py -X utf8 -B "$pkg/build.py"
& $py -X utf8 -B "$pkg/verify_sources.py"
& $py -X utf8 -B "$pkg/self_check.py"
& $py -X utf8 -B "$pkg/make_prelaunch_manifest.py"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$pkg/test_preflight_receipt.ps1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$pkg/test_checker_receipt.ps1"
```

The builder verifies two changed cells across 236 flattened source cells. The verifier checks 47 accepted published source files against both local disk and Git at base `1a80bbe5bcfb0351f27c55c7e0cf665bc761e4c6`, 55 accepted raw seals, five closures and five invocations, plus installed and catalog pins. It preserves the C02/C01 `.gitignore` CRLF local identity separately from the LF Git blob identity. The self check replays 5,210 accepted parent report cells and a 5,210-cell **synthetic** crew-zero parser/report fixture, with 21 direct checks; the latter is not a native observation. The two PS5 receipt checks produce 33 and 15 rejections respectively, using production receipt parsers without SIMLOX. The manifest command only checks exact bytes after the one-time author freeze.

Original accepted raw runs remain under `C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C02-joint-resources-v1.0.2\runs\` and the C01 cap0 path named in `contract.json`. Retrieve those exact sealed directories before running source verification; no regenerated or copied substitute is accepted. The contract lists SHA-256 and byte size for each raw file, closure and invocation. The C02.var03 classification package and accepted C02/C01 source files must likewise retain their published identities.

`make_prelaunch_manifest.py` is a **prepublication exact-source gate** and checks the live root publication-index snapshot. After a later catalog append, sealed read-only replay uses `verify_sources.py --sealed` with the explicitly archived, byte-identical selection catalog and owner receipt in `preserved-context/`, and the child closure's frozen before/after source maps. The historical catalog pin is never silently reinterpreted as the later live catalog.

Only after independent exact-file static review may root invoke the pure preflight under actual SSH PowerShell 5 session 0, with stdin closed, using the pinned file:

```powershell
ssh -n -o BatchMode=yes user@127.0.0.1 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\C02-var01-personnel-zero-v1.0.1\run_native_ssh.ps1" -PreflightOnly'
```

That path must write one unique `review/preflight-ssh0-*.json`, require an absent `c02-var01-v101-personnel0-ssh-20261007-01` run directory, and start zero SIMLOX children. A separate independent `GO_PRELAUNCH` file must bind the exact manifest, runner, validator, input, source map, preflight receipt and independent replay method before root invokes the same file without `-PreflightOnly` for its one authorized child. An unapproved or failed child is never retried with that run ID.

After native execution, read-only replay checks the four native steps and two Python checks, exact integer OS exits and session 0, converter context, typed physical events, all 10,420 parent-plus-child report cells, and sealed source/raw before and after. The resulting `closure.json` and any `failure-seal.json` preserve failure evidence. If a path, Git byte identity or SHA differs, restore the exact original dependency; if import/export or converter rejects, preserve raw and record NO_GO; if an event, ledger or numeric cell violates its predeclared gate, preserve the run and use a new version only after a new contract and review. No product runtime, GUI, cross-engine, performance or general resource law is claimed.
