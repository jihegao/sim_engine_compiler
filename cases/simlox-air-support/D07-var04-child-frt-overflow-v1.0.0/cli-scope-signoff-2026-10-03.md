# D07.var04 child KM FRT exceeds mother: CLI scope sign-off (2026-10-03)

**Decision:** `native_converter_rejection_accepted_cli_scope`, `reusable_published` for one installed-LRU KM rate exceeding its mother system rate on the installed SIMLOX 2017 executable. This is a bounded converter boundary; no simulation behavior is accepted.

## Frozen input and valid boundary

The accepted [D07.var02 valid parent](../D07-var02-dual-opid-v1.0.0/cli-scope-signoff-2026-10-03.md) input SHA-256 is `f89c02d4f3868dd97862998685933208145782f283e21da696307a7be017250d`. The [D07.var04 input](native-input.json) SHA-256 is `beb85438bb30a75094cde6558bf87709abb6663bc3a0655b694e7482fba459c2`. The [exact parent diff](parent-diff.json) SHA-256 is `c2b2185f3d9ae2d3f5426a85a2ea4cd863cde74bba22ce506c9d7b9dc42ba392`: only `ItemFailureRate.KM` changes 5000→10000 per million, plus the description. One `TEACH-LRU-01` is installed under `TEACH-AIR-01`; the mother `SystemFailureRate.KM` remains 5000. Both OPHOURS rates, custom KM utilization, mission schedule, repair, stock and seed remain fixed.

The installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` (PDF pp. 246–247, 257–258) says the summed subitem FRT may not exceed its mother rate and multi-OPID cases do not support removal-rate-factor relief. The installed dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. These proprietary sources are not uploaded. The [pre-run contract](contract.json) did not assume an error number; it required a causal child-versus-mother rate rejection.

## Guarded native diagnostic

Run `d07-var04-child-frt-v100-ssh-20261003-01` used session-0 SSH, host-wide `Global\SimloxIssue18NativeQueue`, GUI PID 13340 identity checks, and `UsePrelifeLog=NO` checks. Import/export preserved all **21 populated source tables** exactly. Native calculation logged **Errors 1, Warnings 1 (#108), Notes 0** and Item **error #2041**: `The sum of item failure rates exceeds failure rate of system: TEACH-AIR-01 (KM)`. The calc process returned exit code zero, but its `.sxo` is only four bytes; no native event log or report was produced. The accepted D07.var02 parent is the earlier valid boundary control.

The [author replay](review/author-rejection-validation-2026-10-03.json) passes **59/59** checks. A separate [independent read-only replay](review/independent-readonly-2026-10-03.json), implemented in its own [script](review/independent_readonly.py), passes **110/110** checks and returns bounded GO. Nine raw files, invocation and closure remain in ignored local `runs/`; the [evidence index](evidence-index.json) seals their hashes. Closure SHA-256 is `b262808c8e11ecf266792d4be890d55e6993d1d2c50c6f152f17625e8ac4ee27`; the invalid four-byte SXO SHA-256 is `2a2d5e177502c5a794270deadd8dd755859f202a96d9d27568826ab0b69f984b`.

This scope is one item/system pair, one custom OPID and one mismatch magnitude on one executable. Different rate ratios or structures, error precedence, GUI visual behavior and cross-engine behavior remain unverified. No mission, reliability, maintenance or stock outcome is inferred from the invalid model. Issue #18 remains open.
