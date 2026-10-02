# H01.var03 continuous DAMP CLI scope sign-off — 2026-10-02

**Decision:** Accept one bounded native converter rejection: this installed SIMLOX 2017 converter rejects `DAMP=1` on the accepted A05 `CONTINUOUS` mission. Publish this `H01.var03` compatibility observation only. Issue #18 and the wider H01 checklist remain open.

## Frozen model and execution

- Accepted A05 continuous parent and byte-identical control SHA-256: `997dea5a9cc44bb6fb9c83b23ca5ccf1924851e89146a923bb5748116b7a63ea`.
- DAMP child source SHA-256: `c61974ba269c15afe3e39e76f396d503b08e522b3b97bbad8125e44c3a02071a`. The exact-diff SHA-256 is `50c9b248de8874f911967288aedfd0e46e4d17dd5e6cf59e41f6b906ac5654f2`: three damage tables added, only `ProblemDescription` changed among existing tables.
- The pre-run contract SHA-256 is `2c5842685f35b96be402d93490f4fdc3b0e3e90e92bca0ae7bc0f24c556f75b9`. The installed manual, dictionary and executable hashes are pinned there and checked before and after execution.
- An independent static reviewer approved exactly two serial diagnostic runs after the runner pinned the contract, manual and dictionary SHA-256 values. Both runs used session-0 SSH, `Global\SimloxIssue18NativeQueue`, and the GUI PID13340 identity guard. Each source exactly roundtripped its 13 or 16 authored row tables.

## Native observation

The control `h01-var03-control-v100-ssh-20261002-01` converted with zero errors and warnings #108/#126, produced a valid SXO, event log and JSON report, launched two aircraft at h8 and logged mission success/completion at h12. Its 32 half-hour System and Stock bins cover 0–16; the System ledger integrates eight aircraft-hours of operation with terminal ready2, and Stock shows no backorder.

The child `h01-var03-damp-v100-ssh-20261002-01` converted with one error: `#252 DAMP is not allowed for continuous or extendable type of missions`. Warnings #108/#126 are the same background warnings as in control. The child has a four-byte SXO stub and no `model.log` or JSON report. Its calculation process exited zero, which does not override the converter error. The 12 control and 9 child raw artifacts are SHA-256 sealed locally; their names, byte counts and hashes are bound by `evidence-index.json`.

The author replay passed 68/68 checks. A separate read-only reviewer, with no author-validator import or native invocation, passed 1815/1815 checks and returned GO only for the converter restriction. The author and independent JSON results and reviewer script are sealed by `evidence-index.json`.

## Limits

No child damage or attrition was simulated. This pair does not establish `DAMRT` rate behavior, intermediate `DAMP`, other continuous or extendable configurations, item/system repair, GUI visual behavior, or cross-engine parity. The manual's continuous-mission restriction is corroborated for this exact installed converter and source model; it is not a population or alternate-version claim.
