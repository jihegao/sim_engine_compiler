# A11: explicit formation priority and complete fallback

This package tests two explicitly named formations for one fixed mission, derived from the published A11 mixed-type minimum input. `FORM-AB` uses one `TEACH-AIR-01` and one `TEACH-AIR-02`; `FORM-AA` uses two `TEACH-AIR-01`. The accepted parent retains `MissionSystem.NOS=MNOS=1` for each type, allowing the formation cases to test override of that quantity rule. The [exact diff](exact-diff.json) records all source changes and pairwise deltas.

The published parent input SHA-256 is `4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213`. The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; pages 184–185, 281–282 and 292–294 describe explicit formations, priority and complete-formation search. The proprietary manual remains local.

## Native three-way comparison

| Variant | Deployed aircraft | Priority 1 | Active formation at launch | Aircraft flown |
|---|---|---|---|---|
| `ab-high` | A#0, A#1, B#2 | `FORM-AB` | `FORM-AB` | A#0+B#2 |
| `aa-high` | A#0, A#1, B#2 | `FORM-AA` | `FORM-AA` | A#0+A#1 |
| `b-missing` | A#0, A#1 | `FORM-AB` | `FORM-AA` | A#0+A#1 |

The `aa-high` variant changes only the two `MissionFormation.PRI` values and description from `ab-high`. It selects A+A even though the inherited `MissionSystem` rows request one B, demonstrating explicit formation priority and override in this ready-aircraft setting. The `b-missing` variant leaves AB at priority 1 but removes B deployment; it selects the complete lower-priority AA formation. No incomplete AB formation launches. Its log records the selected AA formation but not the internal rejection of AB; the fallback interpretation also uses the frozen priority values, unavailable B deployment and manual rule. All three missions launch at hour 8 and log success and completion at 10. Each report contains 72 half-hour system and stock bins and four aircraft mission-hours. Terminal ready counts are three, three, and two respectively.

All three runs completed guarded session-0 SSH import, export, calculation and JSON report with zero conversion errors. Source rows/columns roundtrip exactly over 17 populated tables per input. The warnings are #108 (logging) and #126 twice (both teaching system definitions lack items). Raw `.sxi`, `.sxo`, logs, reports, invocation, steps and SHA-256 closure files remain in ignored local `runs/`.

Reproduce source with `python build.py` and `python describe_diff.py`. Replay the sealed evidence using `python validate_native.py` and the independent reviewer in `review/`. The final run IDs are `a11-form-ab-high-20260930-01`, `a11-form-aa-high-20260930-01`, and `a11-form-b-missing-20260930-01`. New native execution requires new run IDs, active GUI PID 13340, verified session-0 SSH and the host-wide `Global\SimloxIssue18NativeQueue` mutex.

```powershell
ssh -o BatchMode=yes 127.0.0.1 powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A11-explicit-formation-choice-v1.0.0\run_native_ssh.ps1' -Variant ab-high -RunId <new-run-id>
```

This scope does not verify same-priority rejection, ALOAA continuation-only behavior, later readiness, reconfiguration, failures, preparation with positive duration, competing missions, group references, GUI-only behavior or cross-engine parity. A11's broader catalog method remains incomplete.
