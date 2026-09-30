# A11: mixed aircraft types with per-type minimums

This bounded A11 case tests `MissionSystem` type-specific quantity requirements. It derives from published A03 1.0.1, retains one fixed two-aircraft mission, and adds a second aircraft type to the unit. The paired control has only the existing total `MissionType.NOS=MNOS=2`; the required input adds `MissionSystem` rows with `NOS=MNOS=1` for each type. [The exact source diff](exact-diff.json) lists every parent change.

The accepted A03 parent source SHA-256 is `d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`. The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; pages 184, 188, and 302–304 define quantity-based type requirements. The proprietary manual remains local.

## Native pair

One unit deploys two `TEACH-AIR-01` aircraft and one `TEACH-AIR-02` aircraft. All three are ready at hour 0. A two-aircraft `BASIC-MISSION` is scheduled at hour 8 for two hours.

| Native observation | Untyped control | Per-type minimum |
|---|---|---|
| Allocated at hour 7 | A instance 0, A instance 1 | A instance 0, B instance 2 |
| Mission launch and logged completion | 8, 10 | 8, 10 |
| Aircraft mission-hours from 72 half-hour system bins | 4 | 4 |
| Ready at simulation end | 3 | 3 |

Both final native runs import, export, calculate, and produce JSON reports with zero conversion errors. Warnings are #108 (simulation log) and #126 twice (both teaching systems have no items). Source rows and columns roundtrip exactly over 13 control and 14 required populated tables. `MSTF`, `MSUF`, and `STMF` each equal one. The contrast supports one type-specific minimum behavior: an untyped two-aircraft total can select two type A aircraft, whereas these `MissionSystem` rows select one of each type.

The result does not establish type preference under shortage or changing readiness, and it does not verify explicit `Formation`, `FormationSystem`, or `MissionFormation` alternatives. `MNOSA`, `ALOAA`, incomplete formations, failures, preparation, resource conflicts, GUI-specific behavior, and cross-engine parity remain unverified. This bounded scope does not satisfy the full A11 catalog plan.

## Reproduce

Run `python build.py` and `python describe_diff.py` to check the frozen inputs and exact parent/child diff. The final raw runs are `runs/a11-control-20260930-02` and `runs/a11-required-20260930-02`. Their `.sxi`, `.sxo`, logs, raw reports, invocation, steps, and SHA-256 closures remain local and ignored by Git. Replay them with `python validate_native.py` and the independent reviewer under `review/`.

Fresh native execution requires the local SIMLOX installation, pinned source hashes, active GUI PID 13340, session-0 SSH and the host-wide `Global\SimloxIssue18NativeQueue` mutex. Use a unique new run ID for each variant:

```powershell
ssh -o BatchMode=yes 127.0.0.1 powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A11-mixed-type-minimum-v1.0.0\run_native_ssh.ps1' -Variant control -RunId <new-run-id>
ssh -o BatchMode=yes 127.0.0.1 powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A11-mixed-type-minimum-v1.0.0\run_native_ssh.ps1' -Variant required -RunId <new-run-id>
```
