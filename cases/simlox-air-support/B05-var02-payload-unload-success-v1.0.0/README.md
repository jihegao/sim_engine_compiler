# B05.var02: unloading is skipped after a successful payloaded mission

This success-branch pair derives from published [B02 serial preparation](../B02-serial-preparation-v1.0.2/evidence-2026-09-29.md), parent input SHA-256 `fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34`. Both variants put predefined `<PAYLOADING>` in the first ten-minute preparation step before one two-hour mission and use a ten-minute post-mission turnround task. The control's turnround subtask is ordinary `SERVICE`; the child uses predefined `<UNLOADING>`. Other pairwise source changes are descriptive text only. The pre-run [contract](contract.json) and [exact diff](exact-diff.json) capture the intended comparison.

| Event | Ordinary SERVICE control | Built-in `<UNLOADING>` child |
| --- | --- | --- |
| PAYLOADING preparation | Performs 7–7.16667 | Performs 7–7.16667 |
| Remaining preparation | SERVICE 7.16667–7.5 | Same |
| BASIC mission | Succeeds 8–10 | Succeeds 8–10 |
| Turnround SEQ1 | SERVICE performs 10–10.1667 | UNLOADING explicitly `skipped` at 10 |
| Aircraft ready at base | 10.1667 | 10 |

The child still logs a turnround task start/end at hour 10. The accepted contrast concerns positive subtask work and readiness duration, not the existence of a task object. The manual says `<UNLOADING>` runs only after `<PAYLOADING>` when the mission fails. This pair proves its **success-side omission** in one deterministic mission. Positive unloading after a failed mission is a separate unmet B05.var02 branch; payload quantity and internal state are unreported.

Guarded session-0 SSH run IDs `b05-var02-ordinary-control-20260930-01` and `b05-var02-unloading-20260930-01` have closure SHA-256 `e5cddeadb8a4c1cf4519b604027e9379e75b4edaac575f2ea9417b9a5fc6b732` / `88dd3d9838902c6b2c43949f1f729c964e724368ad63a15fff1cc2d2de702b03`. Both complete import, export, calculation, report and exact source roundtrip with zero conversion errors, expected warnings #108/#126 and 18 populated source tables preserved. The host-wide mutex and sole GUI PID 13340/session 1 guards held. Raw `.sxi`, `.sxo`, logs and reports remain local under ignored `runs/`.

Each report has 72 half-hour system and stock bins through hour 36. Summary and stock series are identical. The only system-bin difference is 10–10.5: the ordinary control is ready for 2/3 of the bin and in turnround for 1/3; the child is ready for the full bin with zero turnround exposure. One aircraft is ready at the final bin. The installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; printed page 226 states the payloading/unloading condition, pages 400–404 define allowed built-in IDs and task breakdown syntax.

Rebuild with `python build.py` and `python describe_diff.py`; replay local sealed runs with `python validate_native.py` and [the independent read-only reviewer](review/independent_readonly.py), which passed 171/171 checks. Fresh native execution requires unique run IDs, session-0 SSH, the global Issue #18 mutex and preserved GUI. Failed missions, payload state/quantity, resources, remote PM, GUI-only behavior and cross-engine parity remain unverified.
