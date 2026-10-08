# Read-only reproduction before native execution

Use the bundled Python runtime with `-X utf8 -B` from this directory. These commands read the original accepted sources and raw files; they do not launch SIMLOX:

```powershell
python -X utf8 -B build.py
python -X utf8 -B source_gate.py --mode live --arm control_out1
python -X utf8 -B self_check.py
python -X utf8 -B review/independent_replay.py --pure-source
python -X utf8 -B review/independent_self_check.py
python -X utf8 -B make_source_inventory.py
python -X utf8 -B make_prelaunch_manifest.py --arm control_out1 --mode live --provisional
```

`--provisional` checks the draft source inventory in memory. After root freezes the owned source files, root writes `source-inventory.json` once and then the arm's `prelaunch-manifest-control_out1.json` once. A dry rebuild must be byte-identical. The arm-specific preflight and native commands require separate independent decisions; this guide does not authorize them.

After a successful, sealed control run and independent control GO, the child manifest adds the 25 mandatory control originals and its control GO receipt. The child then needs its own current-source, GUI, mutex, SSH, and absent-run preflight. A failure or missing control seal stops the pair. Original accepted raw paths and future run files are mandatory; inert copies of rejected drafts cannot substitute for them.

The two synthetic logs in this package exercise parser branches only. The independent reader's sealed modes must later parse original native bytes directly. Report expectations combine source and typed-event calculations with the bounded presentation constants declared before either new run. The 5,210 cells per arm include metadata, exact zero/null/discrete values, 72 time bins, and exact binary32 resource means.
