# A12.var04: transfer during active preparation

This pair derives from published [A12 simultaneous priority contention](../A12-mission-priority-contention-v1.0.0/cli-scope-signoff-2026-09-30.md), parent input SHA-256 `300f3129b1f5d78018ad00875b545ffc1d7619dde5c3086c7a8bf0abb145094a`. It keeps the same A+A+B pool, typed A+B minimum, 0.5-hour fixed preparation and two mission types. BASIC calls at 7 for an hour-8 start; SECOND calls at 7.25 for an hour-8.25 start. The `early-high` control gives BASIC priority 1 and SECOND priority 2; `late-high` swaps those values. Apart from descriptive text, the pair changes only those priorities. The [contract](contract.json) and [exact diff](exact-diff.json) were frozen before native execution.

| Event | `early-high` control | `late-high` transfer |
| --- | --- | --- |
| BASIC A#0+B#2 preparation begins | 7 | 7 |
| SECOND calls and takes ready A#1 | 7.25 | 7.25 |
| B#2 preparation under BASIC | Continues to 7.5 | Ordered stopped at 7.25 after 0.25 hour |
| B#2 transfer | None | BASIC gives away; SECOND preassigns, then allocates after same-time proportional turnround marker, reduction factor 0.5 |
| SECOND A#1 preparation | 7.25–7.75 | 7.25–7.75 |
| SECOND B#2 preparation | None | 7.25–7.75 |
| Cancelled mission | SECOND at 8.08333 | BASIC at 7.83333 |
| Successful mission | BASIC 8–10 | SECOND 8.25–10.25 |

The late-high raw log directly shows B#2 preparing for BASIC before 7.25, its original task ordered to stop and stopped, BASIC giving it away, SECOND preassigning it, and a new preparation before SECOND's launch. The proportional turnround has **zero observed duration** because this model has no positive `MissionTurnround` row; its reduction factor 0.5 does not imply positive elapsed work. This is an active-preparation confiscation slice, not a general selection-order or turnround-duration rule.

Guarded session-0 SSH run IDs `a12-var04-early-high-20260930-01` and `a12-var04-late-high-20260930-01` have raw closure SHA-256 `c02b66fb1e2f7853855eef1d4f31fc3729bdcd20997b6c6879c415e7426e0023` and `0539f1c405992c584891dc1639ce92679ea63cd55ca4a4df5afbc325cd96385f`. Five native steps passed per run, with the host-wide mutex and GUI PID 13340/session 1 preserved. All 16 populated source tables roundtripped exactly; conversion logged zero errors, warning #108 and two #126 warnings. Raw `.sxi`, `.sxo`, logs and reports remain local under ignored `runs/`.

The 72 half-hour system bins reconcile event-derived readiness, assignment, preparation and operation. The control accumulates 1.5 preparation aircraft-hours; the transfer child accumulates 1.75, including B#2's interrupted 0.25 hour. Both have four operation aircraft-hours, one successful mission out of two called, no observed failure/PM or stock demand, and three aircraft ready at hour 36. `STREQ` integrates to four hours and has the same series in both runs, but its edge bins differ from actual flight occupancy; its precise semantics remain unresolved. `NSYMO` and `STACC` track the observed flights.

Rebuild source with `python build.py` and `python describe_diff.py`, then replay sealed runs with `python validate_native.py` and the independent read-only reviewer. Fresh native execution requires unique run IDs, session-0 SSH, the global `Global\SimloxIssue18NativeQueue` mutex and the preserved GUI. The installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; printed pages 184–187 describe active-preparation confiscation and proportional turnround. Predefined refuelling/payload subtasks, positive unpreparation duration, resource waiting, equal-priority ties, GUI-only behavior and cross-engine parity remain unverified.
