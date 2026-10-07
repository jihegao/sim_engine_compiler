# Reproduce the C09.var03 retrospective replay

This package reads six previously accepted runs. It does not calculate a new model. The [evidence index](evidence-index.json) contains package-relative `source` byte pins and an `accepted_raw_runs` map with every closure, invocation, and raw file SHA256/size. The frozen [contract](contract.json) identifies the original accepted runs and their role.

The three C09.var04 arms are local, remote, and remote-disabled under `../C09-var04-remote-maintenance-resource-v1.0.0/runs/`. The C03 staffing-2 prerequisite run is at the absolute local path in `contract.prerequisites.C03_direct_parent.accepted_run.path`; the A17 and D01 instructional runs are at their package-relative paths in that same contract section. These accepted run directories remain local and are not copied into this package or published as Git blobs. A checkout without those runs cannot reproduce the raw replay until the sealed originals are restored to the pinned paths. Verify all six `closure.json` and `invocation.json` records plus the 71 raw entries against `accepted_raw_runs` before interpreting the result.

The source comparison is coupled: local has BASE-01 P-MECH, remote has BASE-02 P-MECH with TFRS `0.25`, TTRS `0.5`, TTRSS `0.125` and ENRMS `Y`, and disabled retains that remote source with ENRMS `N`. Read the three pinned native inputs and accepted `exact-diff.json` together. Changing a location, capacity, transfer setting, seed, or repair duration would test a different source; it requires a new frozen contract, distinct run IDs, and fresh independent review before any native work. Replacing a missing accepted run with a recalculation would also be new evidence, not reproduction of this classification.

From this package directory in PowerShell, run:

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py .\check_reclassification.py
& $py .\self_check.py
& $py .\review\independent_replay.py
& $py .\make_evidence_index.py > $null
```

Expected author output is `decision: GO_BOUNDED`, `checks: 16212`, `report_cells: 15630`, and an empty `failures` list. The self-check reports `negative_mutations_rejected: 9`, `scalar_probes: 6`, and `baseline_cells: 5210`. The independent replay has its own `GO_BOUNDED`, 15,892 checks, 5,210 report cells per arm, and zero failures in [independent-verdict.json](review/independent-verdict.json). The index builder exits successfully only when the author and independent verdict SHA values, all current source/raw pins, and the full-cell gates still match. `--write` regenerates the deterministic index; ordinary use reads without writing.

Interpret failures by the first failed gate:

- **Source or Git pin:** Check the listed path, byte count, SHA256, and frozen base commit. CRLF changes alter hashes even when parsed content is equal. Do not normalize a sealed file to force a pass.
- **Missing raw file or closure:** Restore the original accepted run at the exact contract path, then compare its closure and raw SHA/size map. A newly calculated replacement run is different evidence.
- **Native JSON parser:** The native report may contain trailing commas. `native_json.py` removes only commas outside quoted strings in memory; the raw report remains untouched. A parse failure outside that syntax is a failure, not permission to rewrite raw bytes.
- **Roundtrip or converter attribution:** Inspect the sealed `roundtrip-validation.json` and `run.log`. The gates expect 31/32/32 whole tables, 22/23/23 tables with authored rows, exact warnings #108 Control rec1 and #126 System rec1, and notice #292 ResourceRemoteSupport rec1 for remote/disabled.
- **Event/ledger:** Inspect `model.log` physical line order. A failure at h8.28243/8.46988 differs from the h8.53243 return/request events. At h9.28243 task 2 deallocates P-MECH quantity one before task 3 retests, rebooks, and starts. A changed order, station, quantity, or repair duration defeats this classification.
- **Report cell:** The oracle derives each expected System/StockTotal/Resource/summary value from source and events. IDs, nulls, counts, zeros, and whole-bin values are exact. Only timestamp-integrated fractional cells have a declared field-specific tolerance; the printed h10.2824 return time explains the largest `0.0001` bound on NR/NRA/NRRT. Inspect a reported table/row/field mismatch rather than widening a global tolerance.

The result concerns one fixed-seed pool-quantity trace at printed time resolution. It does not prove a persistent individual person ID, universal event priority, lender shortage response, TTRSS rule, or GUI behavior. The shared `../publication-index-v1.json` determines publication state; this guide records reproducibility regardless of catalog status.
