# Read-only classification replay

Use the bundled Python runtime and run these commands from the repository root. They read the already accepted I04.var03 original evidence; they do not launch SIMLOX or run an accepted checker.

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$case = 'cases/simlox-air-support/I04-var09-arrived-system-next-mission-v1.0.0'
& $py -X utf8 -B "$case/source_gate.py" --mode sealed
& $py -X utf8 -B "$case/classify.py" --mode sealed
& $py -X utf8 -B "$case/self_check.py"
& $py -X utf8 -B "$case/review/independent_classifier.py" --sealed
& $py -X utf8 -B "$case/review/independent_self_check.py"
& $py -X utf8 -B "$case/make_evidence_index.py"
```

The sealed gate checks the current catalog metadata and the first 498 accepted entries against the owned historical local and Git archives. It rehashes the accepted parent's indexed sources, mandatory raw/preflight originals, 456 prelaunch roles, 403 current disk/Git source pairs and 76 inherited dependency pairs. Missing mandatory host originals, including the two private local-only app context files, stop full replay. The `--mode live` source gate is only for the exact prepublication catalog 498 state; it is expected to reject a later appended catalog.

The classifier checks the original 118-line log and selected original report cells. The self-check mutates private in-memory copies below the outer byte pin and verifies that wrong identity, time, owner, transfer, mission and typed report cells reject. Its rejected clones are synthetic and are not additional native runs.

The final index command checks the saved index against the current source bytes, the owned small proof copies, and the four mandatory originals from the proof-custody write. It uses the sealed source gate and captured receipts; it does not rerun either classifier.

The previously accepted parent run ID is `i04-var03-idle-system-between-v101-ssh-20261008-01`. This classification has its own ID, `i04-var09-arrived-system-next-mission-v100-20261008-01`, and no new native run directory. The accepted parent package's prelaunch instructions are historical and must not be treated as a request to relaunch that run.
