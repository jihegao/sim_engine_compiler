# Read-only sealed replay

From the repository root, use the bundled Python executable. The commands below do not start SIMLOX or change the sealed run:

```powershell
$py='C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$case='cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0'
& $py -X utf8 -B "$case/build.py"
& $py -X utf8 -B "$case/verify_sources.py" --mode sealed --manifest "$case/prelaunch-manifest.json"
& $py -X utf8 -B "$case/make_prelaunch_manifest.py" --sealed
& $py -X utf8 -B "$case/postrun_context.py"
& $py -X utf8 -B "$case/review_proof_context.py"
& $py -X utf8 -B "$case/make_raw_custody.py"
& $py -X utf8 -B "$case/postrun_audit.py"
& $py -X utf8 -B "$case/review/independent_replay_v2.py"
& $py -X utf8 -B "$case/review/independent_self_check.py"
& $py -X utf8 -B "$case/make_evidence_index.py" --dry
```

The owned 492-entry catalog archive and distinct base Git blob stay exact. The live catalog may grow only with type-exact preservation of its metadata and first 492 entries and unique publication IDs; every sealed replay enforces that prefix. The original prelaunch catalog byte pin is point-in-time evidence, not a postpublication demand that the live file remain 492 entries. The rebuilt evidence index remains byte-identical after a valid append.

The 452 accepted source references are checked against local bytes and pinned Git blobs. All 144 prior accepted/context/failed-witness raw records and all 25 child run files are mandatory at original paths. The 32 small postrun and nine independent proof copies remain mandatory inside this package; corresponding ignored `tmp`/transport originals are checked when present. Original v1 independent postrun failure and v2 repair have distinct files and hashes. The prospective [README](README.md) is historical and is not a postrun acceptance claim.
