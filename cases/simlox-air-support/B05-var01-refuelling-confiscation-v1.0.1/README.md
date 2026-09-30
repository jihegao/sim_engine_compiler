# B05.var01: completed refuelling is skipped after preparation transfer

This bounded pair derives from published [B02 serial preparation](../B02-serial-preparation-v1.0.2/evidence-2026-09-29.md), parent input SHA-256 `fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34`, and uses the active-preparation transfer mechanism already observed in [A12.var04](../A12-var04-active-preparation-confiscation-v1.0.0/cli-scope-signoff-2026-09-30.md). The frozen pair differs only in descriptive text and the first `TaskBreakDown` subtask reference: ordinary `INSPECT` in the control, predefined `<REFUELLING>` in the child. Both retain the ten-minute first step, twenty-minute `SERVICE` second step, one aircraft, BASIC priority 2 and SECOND priority 1. The [contract](contract.json) and [exact diff](exact-diff.json) were fixed before v1.0.1 native execution.

| Event | Ordinary INSPECT control | Predefined `<REFUELLING>` child |
| --- | --- | --- |
| First BASIC mission | Prepares 1–1.5, flies 2–4 | Same; first refuelling step performs 1–1.16667 |
| Second BASIC preparation | First step 7–7.16667; `SERVICE` starts 7.16667 | Refuelling performs 7–7.16667; `SERVICE` starts 7.16667 |
| Higher priority SECOND calls | 7.25; takes aircraft during BASIC's active `SERVICE` | Same |
| SECOND first step | INSPECT repeats 7.25–7.41667 | Refuelling explicitly `skipped` at 7.25 |
| SECOND `SERVICE` and preparation end | 7.41667–7.75 | 7.25–7.58333 |
| Outcome | BASIC cancels at 7.58333; SECOND flies 8.25–10.25 | Same |

The native log names the built-in refuelling subtask and its `skipped` event. The controlled source difference and paired native run support omission after an already completed refuelling step on the confiscated aircraft. Neither the input nor the output exposes tank quantity or consumption, so this package does not claim a measured fuel state or a general fuel rule. The first preparation also performs refuelling despite the aircraft initially being ready.

The two sealed session-0 SSH run IDs are `b05-var01-v101-inspect-control-20260930-01` and `b05-var01-v101-refuelling-20260930-01`, with closure SHA-256 `370ee08fc6542b7b70c2d246ee6287638110ea88ec88c8bd1c09c00d649fef00` and `d2b4fc4e533afee83faa3a67d0674ea32b38c8107bf5381a9ba630bead4ea037`. Five guarded native steps pass in each run, with zero conversion errors, warning #108 and #126, exact roundtrip of all 17 populated source tables, the global Issue #18 mutex, and GUI PID 13340/session 1 preserved. Raw `.sxi`, `.sxo`, logs and reports remain local under ignored `runs/`.

Both runs have 72 half-hour system and stock report bins through hour 36, the same result summary and stock series, and one aircraft ready in the final bin. The only system series difference is the 7.5–8.0 bin: `NSYMP` is 0.5 in the control versus 0.166667 in the child; `NSYMR` is 0.5 versus 0.833333. The child saves ten minutes of SECOND preparation. Both missions that fly succeed; the lower-priority second BASIC mission cancels.

The earlier v1.0.0 probe is retained locally, unpublished. It explicitly defined `<REFUELLING>` in `SubTaskType`, and native conversion returned error #2013 for a double definition. This v1.0.1 package instead references the built-in ID directly in `TaskBreakDown` and converts with zero errors. The installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; printed page 226 describes refuelling omission after confiscation and pages 400–404 define the preparation task and subtask syntax.

Rebuild with `python build.py` and `python describe_diff.py`; replay local sealed runs with `python validate_native.py` and [the independent read-only reviewer](review/independent_readonly.py), which passed 190/190 checks. Fresh native execution requires unique run IDs, session-0 SSH, the host-wide mutex and preserved GUI. The app-managed Python executable has changed since the runs; each sealed run records matching before/after Python hashes, but exact environment reproduction would require the original binary. Payloading, unloading, remote PM, positive unpreparation time, resource contention, other fuel states, GUI-only behavior and cross-engine parity remain unverified.
