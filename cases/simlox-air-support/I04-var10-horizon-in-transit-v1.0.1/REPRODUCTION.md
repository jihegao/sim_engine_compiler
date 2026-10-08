# Prelaunch read-only checks

Use the local Python runtime shown below. These checks read fixed evidence and do not start SIMLOX:

```powershell
$py = 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$case = 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\I04-var10-horizon-in-transit-v1.0.1'
& $py -X utf8 -B "$case\source_gate.py" --mode live
& $py -X utf8 -B "$case\self_check.py"
& $py -X utf8 -B "$case\make_source_inventory.py" --dry
& $py -X utf8 -B "$case\make_prelaunch_manifest.py" --dry
```

The live source gate is for the point before publication. After an accepted catalog append, use `source_gate.py --mode sealed` and the independent sealed reader specified in the eventual publication guide. The original parent and failed construction histories remain mandatory where the source gate says so.
