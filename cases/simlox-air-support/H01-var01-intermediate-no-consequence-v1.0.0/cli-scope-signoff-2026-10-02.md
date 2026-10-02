# H01.var01 intermediate DAMP CLI scope sign-off — 2026-10-02

**Decision:** Accept one bounded fixed-seed native `DAMP=0.5` mixed-occurrence demonstration: one complete mission without a BATTLE-HIT entry followed by one occurrence in each of two later missions. Publish only this observed H01.var01 slice; Issue #18 remains open.

## Frozen model and execution

- Accepted A02 parent and byte-identical control SHA-256: `84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
- Child SHA-256: `0c01a03883341e58239bbf5f69b0486e03c6a59f2dc1d8aa18a4941361858d91`. It adds one BATTLE-HIT DamageType, one MissionDamage `DAMP=0.5`/`DAMRT=null`, and one `<ATTRITION>/PROB=0` DamageItem. Only `ProblemDescription` changes among existing tables. Exact-diff SHA-256: `f0d1d4844c66b0d9a7cfd248bbee91153c020c8f7dba130984f21a6035e73838`.
- Pre-run contract SHA-256: `68448f0445ef611dfbb63e72ae387915d21e521eacdd27e17ed6368e9011ec7c`. It required at least one occurrence and one non-occurrence across the three seed1 missions before any native run; zero or three events would have remained diagnostic. No seed search was performed.
- An independent static reviewer approved two serial guarded diagnostics. Both used session-0 SSH, `Global\SimloxIssue18NativeQueue`, and GUI PID13340 identity checks. Each exactly roundtripped 13 or 16 authored row-containing tables, including three all-null placeholders, with zero converter errors and warnings #108/#126.

## Native observations and reconciliation

The control `h01-var01-intermediate-control-v100-ssh-20261002-01` logs no damage and completes missions h8–10, h20–22 and h32–34. The child `h01-var01-intermediate-child-v100-ssh-20261002-01` also completes all three. Its full first-mission log has no BATTLE-HIT entry; this absence, together with complete mission start/success/completion markers, supports a non-occurrence for that mission. It logs one BATTLE-HIT on the sole aircraft at h20.1366 in the second mission and one at h33.1446 in the third. Both are strictly in flight, with no preparation-stage event, attrition, abort or cancellation.

Each arm has 72 aligned half-hour System and Stock bins through h36, six aircraft-hours of operation, terminal ready1, and zero backorder. The child's `SystemResults.NDAM` records one occurrence in [20,20.5) and one in [33,33.5). The control records zero. Every other System cell and every Stock and ResultSummary cell matches between arms. The 12 raw artifacts from each arm are SHA-256 sealed locally by `evidence-index.json`.

The author replay passed 91/91 checks. A separate standard-library read-only reviewer with no author-validator import or SIMLOX invocation passed 7,750/7,750 and returned GO for this bounded pattern. Their code and verdict are sealed by `evidence-index.json`.

## Limits

One seed and three Bernoulli opportunities show a realized 0/1/1 event pattern, not that the population frequency equals 0.5, nor statistical independence or an event-time distribution. The zero-probability consequence leaves attrition, downstream item/system damage and repair untested. Other probabilities, formation sizes, GUI visual behavior and cross-engine parity remain unverified.
