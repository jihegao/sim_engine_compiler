# Read-only reproduction and guarded run

Status: contract accepted for construction only. No I03.var06 child has run. The native step requires an exact frozen bundle, independent pure preflight review, actual SSH PowerShell 5 `-PreflightOnly` receipt, and a separate independent GO_PRELAUNCH bound to that receipt. Root owns execution.

## Restore accepted evidence

Restore the original accepted ignored run directories named in `contract.json` under `source_lineage.accepted_parent_and_context_raw` (59 records) and `accepted_secondary_context_run_files` (59 records), including their six closures and six invocations. The verifier requires these exact original paths, lengths and SHA-256 values; it does not substitute synthetic runs or rerun the accepted native cases. Restore the accepted source paths at the base Git commit specified by the contract. Distinct local and Git byte identities are checked separately. Installed SIMLOX executable, manual and dictionary must also match their pinned bytes.

The 12 root context receipts and historical 491-entry catalog are preserved as byte-identical owned copies listed in `root-context-custody.json`; available originals are checked separately. Later catalog entries may append only with the archived first 491 entries and typed metadata intact. The original source catalog and the Git blob are distinct identities. The frozen contract audit belongs to the model-absent contract stage and is not a post-construction replay command.

`helper-root-custody.json` names 28 historical root helper/probe records. It requires 26 small owned byte-identical copies and checks the original tmp path when present. The two 1,310,720-byte SSH0 binary fixture streams remain at their original tmp paths and are pinned as raw context by SHA/size; they are not published as source files. Their absence in a fresh checkout does not replace the mandatory accepted SIMLOX run files. The preserved first root wrapper NO_GO and the supplemental no-rerun byte adjudication remain distinct.

## Static checks

Run these from this package with the bundled Python at `C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B .\build.py
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B .\copy_helper_context.py
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B .\verify_sources.py --mode live
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B .\test_sealed_catalog.py
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -B .\self_check.py
```

The builder verifies its existing input and exact two-cell diff without rewriting them. The verifier checks 192 accepted parent source pairs, 22 dependency/context pairs, 118 accepted run records, three installed files, the catalog archive and child input. The catalog test accepts a valid in-memory append and rejects live prelaunch drift plus prefix/type/duplicate changes. Self-check must reconcile the synthetic 5,210-cell report and reject direct event, source, report, JSON and metadata mutations. PowerShell 5 test files exercise the production checker, preflight receipt and binary child capture functions without SIMLOX.

After the final independent method SHA is frozen, `make_prelaunch_manifest.py` without `--write` must reproduce `prelaunch-manifest.json` exactly. The manifest is a prelaunch snapshot. A later authorized publication append is handled by `make_prelaunch_manifest.py --sealed` and `verify_sources.py --mode sealed --manifest prelaunch-manifest.json`, using the exact owned historical catalog archive and live prefix check. The single historical catalog source entry retains its archived SHA; the live catalog may only append entries without changing its old typed prefix or metadata.

## Execution boundary

Root runs only the pinned neutral `ssh_transport.py preflight` for the actual SSH5 zero-native preflight. It writes a unique ignored transport evidence directory containing the original SSH stdout/stderr bytes, lengths and hashes, integer outer exit and UTC times. The runner must observe SSH session 0 and `sshd.exe` ancestry, the exact protected responding GUI, active WTS session, free mutex and absent reserved run path. The preflight receipt records `native_process_started=false` and the exact source map. The actual native `ssh_transport.py native` is allowed only after independent GO_PRELAUNCH binds that receipt, manifest, runner, validator, input and independent replay method. The runner makes one unique six-stage child run and naturally joins every native/checker child while holding the mutex; no kill, timeout after connection, or retry is used.

The run directory, if created, remains ignored and sealed with original binary stdout/stderr for every step, actual child PID/session/integer OS exit, before/after source hashes, raw artifacts, invocation and closure. A failed step preserves its streams and failure seal. Any missing pin, mismatched source, parser exception, unexpected event/report cell, nonzero or missing integer OS exit, lost binary capture, GUI or ownership change is NO_GO. A new version and review would be required to alter a frozen gate. The historical accepted parent and prior publication failures remain unchanged.
