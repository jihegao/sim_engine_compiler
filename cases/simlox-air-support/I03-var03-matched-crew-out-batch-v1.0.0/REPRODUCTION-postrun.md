# Read-only sealed replay

Run these commands from the package directory with the bundled Python (`-X utf8 -B`). They read original bytes and do not start SIMLOX:

```powershell
python -X utf8 -B source_gate.py --mode sealed --arm control_out1
python -X utf8 -B source_gate.py --mode sealed --arm child_out2
python -X utf8 -B validate_native_cli.py runs/i03-var03-control-out1-v100-ssh-20261008-01 control_out1
python -X utf8 -B validate_native_cli.py runs/i03-var03-child-out2-v100-ssh-20261008-01 child_out2
python -X utf8 -B review/independent_replay.py --sealed-both
python -X utf8 -B review/independent_self_check.py
python -X utf8 -B copy_postrun_context_v2.py
python -X utf8 -B copy_catalog_regression.py
python -X utf8 -B make_raw_custody.py
python -X utf8 -B make_failed_copier_relocation.py
python -X utf8 -B make_evidence_index.py --dry
```

The final index builder's default invocation verifies byte equality with the saved `evidence-index.json`; `--dry` computes it without writing. The dry output must be identical after an authorized catalog append. Its typed catalog check always requires the owned historical 493-entry archive, its distinct base Git blob, unchanged live metadata and first 493 entries, and unique appended publication IDs. No conditional catalog check is omitted after append.

Original accepted parent/prerequisite raw (112) and both new run directories (25 files each) are mandatory. They may be restored to their declared original paths but cannot be replaced with copies in the proof maps. The inert small-proof copies under `preserved-postrun-context-v2/` and `preserved-catalog-regression/` permit review of temporary receipts when original tmp files are absent; if an original path exists, its bytes must still match. The failed first copier and all partial files are a separate excluded development record.

For publication review, compare the independent paired verdict, two original invocations and closures, both per-arm preflight/approval receipts, original run files, and the index source/raw maps. The original accepted parent run was never relaunched. The paired result is bounded to the described inputs and installed executable.

## Fresh derived work

A new experiment needs a new package version and unique control and child run IDs. Derive both inputs from the accepted I03.var01 parent while keeping its accepted directories untouched. This pair used P-CREW opening RQTY3 in both arms; between the new arms, only OUT TFQTY1→2 and ProblemDescription.PDESC changed. Preserve exact C03/C08 prerequisite source and raw pins, the installed executable/dictionary/manual pins, and the authored source diff. Update and independently review the new contract, input generator, typed event and quantity ledger, complete report oracle, provenance verifier, runner, neutral SSH transport, and source map before any launch.

For a new pair, freeze the control source manifest first. Root checks the existing serial mutex and a fresh GUI PID/session/start identity, then runs an actual SSH5 `-File` zero-native control preflight and obtains a separate independent GO_PRELAUNCH. Root alone launches the control once, lets it exit naturally, seals every original file and obtains independent control GO. Only then may a distinct child manifest pin those control originals; the child requires a fresh source/GUI/mutex/absent-run check, its own SSH5 zero-native preflight and its own independent GO_PRELAUNCH before root launches it. A failed control stops the pair. Never rerun the accepted parent or overwrite an existing run directory.

The original [REPRODUCTION.md](REPRODUCTION.md) records this package's historical prelaunch steps and fixed run IDs. It is retained as evidence, not a command to relaunch those accepted runs.
