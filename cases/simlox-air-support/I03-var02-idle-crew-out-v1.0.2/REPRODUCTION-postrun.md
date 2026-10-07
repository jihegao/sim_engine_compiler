# Read-only reproduction: I03.var02 v1.0.2

Use the bundled Python from the repository root. Each command prints a verdict; none launches SIMLOX or rewrites a frozen verdict or run file.

```powershell
$py = 'C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$case = 'cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2'
& $py -X utf8 -B "$case/postrun_context.py"
& $py -X utf8 -B "$case/make_raw_custody.py"
& $py -X utf8 -B "$case/postrun_audit.py"
& $py -X utf8 -B "$case/review/independent_replay_v3.py"
& $py -X utf8 -B "$case/make_evidence_index.py"
```

Expected outcomes: 19 exact root-context copies; 34 accepted parent/context and 25 sealed child run records; author `GO_AUTHOR_SEALED_REPLAY` with 5,210 child report cells; independent `GO_BOUNDED` with 14,996 checks and 5,210 cells in each arm; dry index hash equal to [evidence-index.json](evidence-index.json), `written:false`. The original author `self_check.py` is a synthetic 5,210-cell/33-rejection static test and never substitutes for the native child. Console line endings can differ from saved LF JSON; compare parsed verdict fields unless checking an explicitly pinned byte identity.

Restore the **original** accepted run records named in [raw-custody-map.json](raw-custody-map.json), including the accepted busy OUT parent's closure and invocation, and all 25 child run files under `runs/i03-var02-idle-out-v102-ssh-20261007-01`. Their size and SHA-256 must match. The 20 accepted source paths, distinct local/Git identities at base commit, and installed executable, manual and dictionary are also mandatory. The native run directories and proprietary installed files are not copied into this package. Missing or corrupt originals require restoration of the byte-identical evidence, never a fresh native rerun or synthetic substitute.

The 19 byte-identical root context and neutral SSH transport copies are mapped in [postrun-context-custody.json](postrun-context-custody.json); these are source-history and transport receipts, not model raw evidence. Exact historical v1.0.0/v1.0.1 and rejected method copies remain in `preserved-v100/`, `preserved-v101/`, `preserved-root-context/` and `preserved-prefreeze/`. Their named owned copies are mandatory; original unpublished `tmp/` or sibling paths are checked if present. The archived 490-entry catalog has a separate exact byte pin; a later live catalog may only append entries while retaining that prefix and all other metadata. The base Git catalog blob has its own distinct pin.

The sealed checker validates original input/export metadata, typed event order and crew conservation, source/event report expectations, closure, six PID/session/integer-exit steps, and before/after source maps. A failed pin is a custody failure. A changed typed edge, metadata/null/count/whole-bin cell, or unclassified formula is a behavior failure; retain the original diagnostic. Any different input, new native call, or wider interpretation needs a separate frozen contract and review. Do not invoke the historical frozen runner or use a previous NO_GO artifact as approval. `README.md` and `REPRODUCTION-v2.md` are prelaunch snapshots; [README-publication.md](README-publication.md) records the bounded postrun disposition.
