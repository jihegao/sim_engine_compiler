# H01.var02 DAMP/DAMRT mutual-exclusion CLI scope sign-off — 2026-10-02

**Decision:** Accept one bounded native converter rejection for simultaneous positive `DAMP` and `DAMRT` in the same MissionDamage row. Publish only this installed-converter compatibility observation; Issue #18 and the wider H01 checklist remain open.

## Frozen model and execution

- Accepted H01.var02 rate source and byte-identical control SHA-256: `947fe484aad8aa8a971160baaddc56489a2cea78e1b0365fe955c59de04c7d65`.
- Simultaneous child SHA-256: `8c11802abd0a2576fe01c1ab8625efd066862561eb6fc0b28ec32eb23c0e4217`. Only `MissionDamage.DAMP` changes 0→1 and `ProblemDescription` changes; `DAMRT=3,000,000` remains. Exact-diff SHA-256: `16e361de224b20e8f4cdb5dbc5c5e949e738566da8388184fd1abd9d289fa8fb`.
- Pre-run contract SHA-256: `2eae1c14cbbd8e60270695c3671d1452c1e6f5d10f3f37a98e2ee495aed01a20`. The installed manual physical pp437–439 states that only one of DAMP/DAMRT may be positive for each mission/damage/system combination.
- An independent static reviewer approved two serial guarded diagnostics. Both used session-0 SSH, `Global\SimloxIssue18NativeQueue`, and GUI PID13340 identity checks. Each exactly roundtripped 16 authored row-containing tables, including three all-null placeholders.

## Native observations

The control `h01-var02-mutual-control-v100-ssh-20261002-01` converts with zero errors, completes all three h8–10/h20–22/h32–34 missions, and logs the accepted 5/2/3 BATTLE-HIT event pattern. Its 72 System and Stock half-hour bins reconcile ten `NDAM` events, six aircraft-hours, and terminal ready1, with no ordinary failures, attrition or abort.

The child `h01-var02-mutual-simultaneous-v100-ssh-20261002-01` has the same 16-table import/export identity but reports one converter error: `#253 DAMP and DAMRT cannot both be used for a certain MTID-DAMID combination`. Background warnings #108/#126 remain. The child leaves a four-byte SXO stub and no model event log or JSON report. The calculation process exits zero, which does not override the converter error. The 12 control and 9 child raw artifacts are SHA-256 sealed locally and bound by `evidence-index.json`.

The author replay passed 71/71 checks. A separate standard-library read-only reviewer with no author-validator import or SIMLOX invocation passed 3,910/3,910 and returned GO for the bounded converter rejection. The reviewer code and verdict are sealed by `evidence-index.json`.

## Limits

This claim concerns the installed converter and the exact positive values/source model. It does not establish behavior in other versions or for every invalid input combination. The rejected child yields no simulated damage or consequence claim. Intermediate DAMP, positive attrition/item/system damage, repair, GUI visual behavior and cross-engine parity remain unverified.
