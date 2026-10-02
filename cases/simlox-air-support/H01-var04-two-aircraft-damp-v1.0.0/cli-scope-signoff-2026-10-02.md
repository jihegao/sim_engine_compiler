# H01.var04 two-aircraft DAMP CLI scope sign-off — 2026-10-02

**Decision:** Accept one bounded native fixed-seed demonstration of one `DAMP=1` damage occurrence on each aircraft in one two-aircraft fixed mission, with no consequence. Issue #18 and the wider H01 checklist remain open.

## Frozen model and execution

- Accepted A03 parent and byte-identical control SHA-256: `d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`.
- Damage child SHA-256: `ca7ce1a2493631202c7c1ee4e5f7e3a5fe2c765b0d016bf47fbdd2751921f28c`. Its added tables specify `BATTLE-HIT`, `DAMP=1`, `DAMRT=null` and `<ATTRITION>/PROB=0`; only `ProblemDescription` changes among existing tables. Exact-diff SHA-256: `fedbb7381a16d7938316a765bbad7dd723628866c57c39c2c8c54b886b4c79af`.
- Pre-run contract SHA-256: `67b0ff49e79f9a16a920fbc5e26b280f9a952f277a9ea35ac2f6b95c2ccd6d7e`. Installed manual, dictionary and executable identities were pinned before and after the runs.
- An independent static reviewer approved the corrected frozen checker and two serial guarded diagnostic runs. Both used session-0 SSH, `Global\SimloxIssue18NativeQueue`, and GUI PID13340 identity checks. They exactly roundtripped 13 or 16 authored row-containing tables, including three all-null placeholders per arm, with zero converter errors and warnings #108/#126.

## Native observations and reconciliation

The control `h01-var04-control-v100-ssh-20261002-01` logs no damage. Both arms allocate aircraft IDs 0 and 1 to the one mission, launch at h8, succeed and complete at h10, and return both aircraft ready. The child `h01-var04-damp-v100-ssh-20261002-01` logs `BATTLE-HIT` on aircraft 1 at h8.17491 and aircraft 0 at h8.78145. Those are distinct times strictly inside the mission. Neither arm logs attrition, abort or cancellation.

Each arm has 72 aligned half-hour System and Stock bins through h36 and integrates four aircraft-hours. `SystemResults.NDAM` in the child records one occurrence in each of the [8,8.5) and [8.5,9) bins. The control records zero. Every other System cell, and every Stock and ResultSummary cell, matches between arms; terminal ready count is two and backorder is zero. The 12 raw artifacts from each arm are SHA-256 sealed locally by `evidence-index.json`.

The author replay passed 89/89 checks. A separate standard-library read-only reviewer with no author-validator import or SIMLOX invocation passed 7,729/7,729 checks and returned GO for this bounded occurrence claim. The reviewer code and verdict are sealed by `evidence-index.json`.

## Limits

One fixed seed with a certain occurrence probability and two aircraft shows per-aircraft event logging and distinct sampled times. It cannot establish statistical independence, a population timing law or behavior at intermediate probability. `PROB=0` means positive attrition, item/system damage and repair are untested. Other formation sizes, GUI visual behavior and cross-engine parity remain unverified.
