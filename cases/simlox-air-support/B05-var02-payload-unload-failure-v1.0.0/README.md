# B05.var02: unloading performs after a payloaded mission aborts

This failure-branch pair derives from the published [B05.var02 successful-mission control](../B05-var02-payload-unload-success-v1.0.0/cli-scope-signoff-2026-09-30.md), parent input SHA-256 `21bd66e3ba54e22fb5d7c7c9b612892faf2999cb873f7dd34483e5880a607c9a`. Both variants add the exact local system-repair row and `System.FRT=300000` per million OPHOURS from published [D01](../D01-system-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md), source SHA-256 `d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450`. The frozen pair differs only in turnround SEQ1: ordinary `SERVICE` versus built-in `<UNLOADING>`, plus description. Both retain positive `<PAYLOADING>` preparation.

| Event | Ordinary SERVICE control | Built-in `<UNLOADING>` child |
| --- | --- | --- |
| PAYLOADING | Performs 7–7.16667 | Performs 7–7.16667 |
| Mission | Starts 8; critical failure aborts it at 9.8829 | Same |
| Aborted mission completes | 10 | 10 |
| Turnround subtask | SERVICE performs 10–10.1667 | UNLOADING performs 10–10.1667 |
| Direct repair | 10.1667–10.6667 | Same |
| Final state | One ready aircraft at 36 | Same |

The child log explicitly names `unloading subtask` with positive work and completion. This complements the [successful-mission branch](../B05-var02-payload-unload-success-v1.0.0/cli-scope-signoff-2026-09-30.md), where the same built-in subtask is explicitly skipped. The contrast is a fixed-seed, one-aircraft native observation; the model does not report payload quantity or internal payload state. Failure onset is stochastic and only its observed time is claimed.

Guarded session-0 SSH runs `b05-var02-failure-ordinary-20260930-01` and `b05-var02-failure-unloading-20260930-01` have closure SHA-256 `1abcbadd3bdef2e8ad7eed94c1f4c72d433893a3067ded52bf2165ac3f026d26` / `6c0e0acdb8156b86db1e766be92c2db7377cba960719e9c46cc02ef54c7b63bc`. Five native steps complete per run with zero conversion errors, expected warnings #108/#126, and exact roundtrip of 19 populated source tables. The host-wide mutex and sole GUI PID 13340/session 1 guards held. Raw `.sxi`, `.sxo`, logs and reports remain local under ignored `runs/`.

Both reports have 72 half-hour system and stock bins through hour 36, and identical result summary, system and stock series across the pair. The system bins record one failure, one repair, a third of the 10–10.5 bin in turnround and two-thirds in repair, then readiness at 10.6667. The installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; printed page 226 gives the PAYLOADING/UNLOADING condition, pages 190–191 and 211–212 describe critical failure/repair, and pages 400–404 define built-in subtask IDs and breakdown syntax.

Rebuild with `python build.py` and `python describe_diff.py`; replay local sealed runs with `python validate_native.py` and [the independent read-only reviewer](review/independent_readonly.py), which passed 183/183 checks. Fresh native execution requires unique run IDs, session-0 SSH, the global Issue #18 mutex and preserved GUI. Other seeds, noncritical failures, payload quantity, resources, GUI-only behavior and cross-engine parity remain unverified.
