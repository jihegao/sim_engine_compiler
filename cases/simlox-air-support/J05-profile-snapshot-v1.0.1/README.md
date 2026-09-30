# J05.var03: continuous intervals and snapshots

This bounded A01-derived case uses three frozen inputs: an unchanged baseline, a direct `SnapshotResultTimes` control, and a `SYSTEM` `ResultCollectionProfile` that mixes continuous intervals and snapshots. The mixed profile records 7.75–8.25 and 9.75–10.25 as half-hour averages, plus instantaneous states at 8.25 and 10.25. Its global snapshot times are 6 and 14, allowing the override to be observed. `SIMPE=36`, seed 1 and mission behavior are unchanged.

The [contract](contract.json), [builder](build.py), [exact diff](exact-diff.json) and [CLI scope sign-off](cli-scope-signoff-2026-10-01.md) bind the input, source and observed result. Fresh guarded native runs passed exact source roundtrip for 13/15/16 populated tables and zero conversion errors. The default JSON report omits snapshot tables. A guarded report-only pass on the sealed `.sxo` files, using a local one-byte copy of the installed default report settings, exposes the native replication snapshot rows. The installed settings file and GUI were not changed. Raw runs and settings remain ignored under `runs/`.

The v1.0.0 triplet with an incorrect `SnapshotResultTimes.SSTIM` key marker remains an excluded local diagnostic. J05.var04 nested/repeated profiles, MISSION result intervals, other result types, GUI display and cross-engine behavior remain unverified.

## Reproduce on the pinned host

Run `python build.py` to verify the frozen inputs. In an authenticated session-0 SSH shell, use `run_native_ssh.ps1` once per variant (`baseline`, `snapshot-control`, `mixed-profile`) with a fresh run ID; the runner enforces the global queue and GUI identity. Run `python make_report_settings.py` to verify the installed default settings fingerprint and create its ignored one-byte local copy. In the same SSH mode, use `report_existing_sxo_ssh.ps1` on the two child `.sxo` files with `-SettingsMode replications` and fresh report run IDs. `python validate.py` and `python review/independent_readonly.py` replay the published run IDs; for new run IDs, compare the resulting source, event, interval and snapshot ledgers against the sign-off. Never edit the installed `Default.sxs`.
