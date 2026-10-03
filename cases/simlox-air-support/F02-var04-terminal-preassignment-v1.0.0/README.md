# Excluded F02.var04 terminal preassignment probe

This [pre-run contract](contract.json) asked for a direct `mission preassigns a system` event before the hour-60 reporting cutoff. The guarded native run converted cleanly and roundtripped all 30 authored populated tables, but the event log instead says `TERMINAL-HOLD mission allocates system` at 59.5 and starts preparation. The positive preassignment gate therefore failed. See [diagnostic.json](diagnostic.json); this package is **not published**.

The source changes from the [accepted active-removal parent](../F02-var04-terminal-repair-v1.0.0/cli-scope-signoff-2026-10-04.md) are exactly `Control.SIMPE` 60→65 and four appended mission rows. The report cutoff stays at 60, so its final `[59.5,60)` bin shows aircraft 1 allocated and preparing and aircraft 0 actively in repair. Preparation completes at 60; the mission cancels at 62 during the longer simulation. These observations can motivate a new, separately frozen allocation case, but they cannot be relabeled as preassignment or inventory reservation.

Raw artifacts remain under the ignored local `runs/f02-var04-preassign-v100-ssh-20261004-01/` path, sealed by closure SHA-256 `64aacad857e5798f2c6503095495ef424e447ee28756d34abc5eaa38e3ae59ed`. GUI PID 13340 was preserved.
