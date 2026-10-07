# Read-only reconstruction

Use the bundled Python executable with `-X utf8 -B`. From the repository root:

```powershell
$py='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$case='cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0'
& $py -X utf8 -B "$case/build.py"
& $py -X utf8 -B "$case/verify_sources.py" --mode sealed
& $py -X utf8 -B "$case/test_sealed_catalog.py"
& $py -X utf8 -B "$case/self_check.py"
```

The 452 accepted source references must match both local bytes and their distinct Git blobs at the pinned base commit. The 144 original accepted/context and failed-witness raw records and three installed files remain mandatory at their original paths. Seven root selection `tmp` originals may be absent in a fresh checkout only when their named byte-identical copies and custody map are present; if an original exists it is checked too. The owned historical 492-entry catalog archive is mandatory. A later live catalog may append entries only when its metadata and first 492 entries remain type-exact and all publication IDs stay unique. Before native, the live catalog bytes must also match the original 492-entry snapshot exactly.

Once the independent reviewer freezes its methods, run `review/independent_replay.py` and `review/independent_self_check.py` with the same Python flags. A sealed child run, if one is later authorized, must be read with the exact manifest and original invocation/closure/raw files; the accepted parent is never rerun. Pure synthetic fixture success is not a native outcome.
