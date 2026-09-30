# A13: one explicit START mission dependency

This version adds one `MissionDependence` START row to an accepted A02-derived, two-aircraft model. The paired control has the same aircraft, mission types, and schedule without that row. Both missions are fixed. This is a bounded behavioral slice of A13, not the entire dependency method.

## Source and parent

- Parent: published `A02.repeated.1.0.0`, source SHA-256 `84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
- Manual: installed SIMLOX 2017 User's Manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, pages 188 and 287–289.
- Source relationship: `exact-diff.json` records every changed cell and the one added table. `build.py` regenerates and checks the two frozen inputs.

## Native configuration and observation

Two ready aircraft belong to `TEACH-UNIT`. `RECON` is scheduled at hour 8 for four hours; `FOLLOW` is scheduled at hour 10 for two hours. Both need one aircraft. The profile delay limit is four hours. The dependent input identifies `FOLLOW` at hour 10 and `RECON` at hour 8 in the `MissionDependence` START row.

| Observation | No-dependency control | START dependency |
|---|---:|---:|
| RECON launch / logged success and completion | 8 / 12 | 8 / 12 |
| FOLLOW assigned aircraft 1 | 9 | 9 |
| FOLLOW launch / logged success and completion | 10 / 12 | 12 / 14 |
| Systems on mission in hour 10–10.5 report bin | 2 | 1 |

The second aircraft is available and assigned to FOLLOW at hour 9 in both runs. The two-hour difference in launch time therefore demonstrates the explicit START launch gate in this model. Both runs import, export, calculate, and produce reports with zero conversion errors and warnings #108 (simulation log) and #126 (teaching system has no items). Source roundtrips preserve 13 populated control tables and 14 populated dependent tables. Each report contains 48 half-hour system bins and 48 stock bins; `MSTF`, `MSUF`, and `STMF` equal 1 in each one-replication result.

The model sets `MSUCPT=0.25` for RECON, but the native log records its `mission success` event at hour 12. This evidence does not locate an earlier internal success point or separate the return event from same-time completion. The manual disagrees on whether the precedent or dependent side must be fixed for START; both are fixed here, so that wording conflict remains unresolved.

## Reproduce and inspect

The local session-0 SSH runner pins source and executable hashes, checks GUI PID 13340, takes the host-wide `Global\SimloxIssue18NativeQueue` mutex, and creates a unique immutable run directory. From this checkout, run one variant at a time with a new run ID:

```powershell
ssh -o BatchMode=yes 127.0.0.1 powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A13-start-dependence-v1.0.0\run_native_ssh.ps1' -Variant control -RunId <new-run-id>
ssh -o BatchMode=yes 127.0.0.1 powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A13-start-dependence-v1.0.0\run_native_ssh.ps1' -Variant dependent -RunId <new-run-id>
```

The sealed accepted candidate runs are `runs/a13-control-20260930-03` and `runs/a13-dependent-20260930-03`. Raw native `.sxi`, `.sxo`, logs, reports, invocation, steps, roundtrip results, and closure SHA manifests remain local and ignored by Git. Earlier `-01` and `-02` exploratory runs are retained locally and excluded from this publication. The source-bound author validator is `validate_native.py`; its result is in `review/author-native-validation-2026-09-30.json`.

Unverified: predecessor failure and incomplete return, multiple dependencies, cross-unit or group identity, repeated mission identity, non-fixed roles, continuous dependencies, GUI-specific behavior, and cross-engine parity.
