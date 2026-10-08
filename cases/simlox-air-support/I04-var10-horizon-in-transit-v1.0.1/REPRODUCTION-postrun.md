# Read-only reproduction

Use the same local repository and installed SIMLOX files recorded in the frozen source map. The mandatory parent, native and preflight originals must be present at their pinned host paths. The private app context originals stay local. These commands do not dispatch SIMLOX or rerun accepted-parent checkers. The explicit independent replay rechecks this child's sealed evidence; the final index command checks bytes and custody.

```powershell
$case = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\I04-var10-horizon-in-transit-v1.0.1'
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$recovered = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i04-var10-root-sealed-replay-v101-20261008\20261008T141626170671Z-ad3cc985\recovered-evidence'
& $py -X utf8 -B "$case/source_gate.py" --mode sealed
& $py -X utf8 -B "$case/copy_postrun_context.py"
& $py -X utf8 -B "$case/make_raw_custody.py"
& $py -X utf8 -B "$case/make_preflight_custody.py"
& $py -X utf8 -B "$case/review/independent_replay.py" --evidence-dir $recovered
& $py -X utf8 -B "$case/make_evidence_index.py"
```

The saved independent replay is the original bounded semantic check. Its original captured receipt and stdout are pinned in the postrun context map. The index command is the final byte-only custody check and verifies the saved index against the current files; after catalog append it must produce the same index bytes. The parent catalog's historical local CRLF and base-Git LF identities are separate pins, while the later catalog is checked by typed immutable prefix.

The first root native capture summary is preserved as a wrapper `NO_GO_PRESERVE_FAILURE`, alongside the captured child transport exit 0 and the later independent `GO_BOUNDED`. The summary is not a reason to rerun native. The v1.0.0 static NO_GO and superseded first 98-row publication context maps are inert history and cannot be substituted for this case's final evidence.
