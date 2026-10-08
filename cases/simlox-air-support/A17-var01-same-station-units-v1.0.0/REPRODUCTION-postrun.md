# Read-only bounded reproduction

These commands are for the controlled host with all mandatory original files present. They do not dispatch SIMLOX, rerun accepted-parent checkers, or create another native run. `source_gate.py` uses read-only Git `ls-tree` and `cat-file` to verify the 41 accepted path/OID/blob pairs.

```powershell
$case = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A17-var01-same-station-units-v1.0.0'
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$recovered = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\a17-var01-root-native-custody-v100-20261008\20261008T172753084781Z-55f294be\recovered-run'
& $py -X utf8 -B "$case\source_gate.py"
& $py -X utf8 -B "$case\review\independent_reader.py" --evidence-dir $recovered
& $py -X utf8 -B "$case\make_evidence_index.py"
```

The independent reader rechecks this child's sealed recovered evidence: exact source and receipt provenance, 25 native files, export topology, converter paths and warnings, full log and report. It is distinct from the accepted-parent checkers, which are not rerun. Once the reviewed canonical index exists, the final command verifies all indexed package bytes without native or semantic execution; before index creation its default mode must fail.

The host must retain the original 61 prelaunch sources, 15 zero-native preflight files, 39 native/PURE/transport files, 25 recovered copies, and 19 publication proof files (15 capture receipts/streams and four source methods), plus their external proof manifest. The package carries two small log copies and 77 small postrun context/proof copies, with exact custody maps. The published package does not contain proprietary manual pages, unrelated app snapshots, full native SXI/SXO, or the full raw report/export. Absence of a mandatory host original means the full sealed replay is unavailable on that checkout.
