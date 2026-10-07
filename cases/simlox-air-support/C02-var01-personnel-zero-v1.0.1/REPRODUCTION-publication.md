# Read-only reproduction — C02.var01 personnel-zero

Work from the repository root with the bundled Python. These commands read existing evidence; they do not launch SIMLOX or rewrite any sealed file.

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pkg = 'cases/simlox-air-support/C02-var01-personnel-zero-v1.0.1'
& $py -X utf8 -B "$pkg/verify_sources.py" --sealed
& $py -X utf8 -B "$pkg/review/independent_replay_v2.py"
& $py -X utf8 -B "$pkg/make_evidence_index.py"
```

Expected results: source verification passes **47 published source identities and 55 accepted raw seals**; independent replay prints `GO_BOUNDED`, `checks: 13434`, `report_cells: 10420`, and no failures; the dry index builder reports the same SHA as `evidence-index.json`. Its source count includes the frozen prelaunch package, the separate reader correction, the excluded v1.0.0 files, and the postrun custody and guide files. The original approved `review/independent_replay.py` is intentionally retained as a failing historical reader; do not run it as the acceptance command. Its [NO_GO record](review/independent-replay-original-no-go-2026-10-07.md) and the [v2 GO review](review/independent-postrun-review-2026-10-07.md) explain the narrow repair.

The [raw custody map](raw-custody-map.json) gives the exact original path, byte size, and SHA-256 for 55 accepted-context raw files and the 23 new child raw files, plus all six run closures and invocations. The accepted C02 runs are under `C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C02-joint-resources-v1.0.2\runs\`; the accepted C01 cap0 path is in `contract.json` and the map. The child is under this package's ignored `runs/c02-var01-v101-personnel0-ssh-20261007-01/`. Restore those exact local run directories before replay. The raw runs, native binaries, and manual are not published in Git, and no newly executed or synthesized substitute is accepted.

The [context custody map](context-custody-map.json) identifies byte-identical, named copies of root selection, instruction, preflight/native driver, postrun, source-freeze, and original BOM failure receipts. Their original `tmp/` paths and archive copies remain distinct identities. The prelaunch `preserved-context/` folder also holds the exact historical catalog and selection receipts. `verify_sources.py --sealed` and independent v2 replay use those **declared** historical keys after the central publication index appends a new entry; they continue to check the current catalog's earlier entries and metadata. The prelaunch `make_prelaunch_manifest.py` and historical `author_postrun_assessment.py` verify the original live-catalog snapshot and are prepublication-only commands. They must not be changed or reinterpreted after catalog append.

Failures have different remedies. A SHA, size, missing-run, or Git/local byte mismatch requires restoration of the original sealed dependency; do not normalize CRLF/LF or rerun native. A malformed closure or missing step/raw seal is a provenance NO_GO. A typed event, order, ledger, report-cell, null, or numeric-bound mismatch is a semantic NO_GO for this classification. Preserve the failing bytes and create a new reviewed version before testing a different source. The specific original-reader BOM failure is preserved separately and does not change the successful native closure or v2's bounded result.
