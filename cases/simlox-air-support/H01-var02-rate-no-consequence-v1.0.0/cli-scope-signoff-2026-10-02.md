# H01.var02 DAMRT repeated-event CLI scope sign-off — 2026-10-02

**Decision:** Accept one bounded native fixed-seed `DAMRT` occurrence demonstration with ten visible same-type events across three fixed missions and zero-probability attrition consequence. Publish only this observed `H01.var02` slice; Issue #18 and the wider H01 checklist remain open.

## Frozen model and execution

- Accepted A02 parent and byte-identical control SHA-256: `84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
- Rate child source SHA-256: `947fe484aad8aa8a971160baaddc56489a2cea78e1b0365fe955c59de04c7d65`. Its three added damage tables specify `BATTLE-HIT`, `DAMP=0`, `DAMRT=3,000,000` per million mission hours and `<ATTRITION>/PROB=0`; only `ProblemDescription` changes among existing tables. Exact-diff SHA-256: `49659229552396b5879b01d683bab6d44fe6adbd57c071dea876dd643aca122c`.
- Pre-run contract SHA-256: `ebdcd55cd3744eef7c88756f233d4c0fb0d978c5340bdc85e983263384852b2d`. Installed manual, dictionary and executable identities are pinned and checked before and after the runs.
- An independent static reviewer approved two serial guarded diagnostic runs. Both used session-0 SSH, `Global\SimloxIssue18NativeQueue`, and GUI PID13340 identity checks. Each exactly roundtripped its 13 or 16 authored row tables with zero converter errors and warnings #108/#126.

## Native observations and reconciliation

The control `h01-var02-control-v100-ssh-20261002-01` logs no damage and three mission starts at h8/20/32 with successes/completions h10/22/34. The rate arm `h01-var02-rate-v100-ssh-20261002-01` retains those mission events and logs `BATTLE-HIT` at h8.18829, 9.0828, 9.32945, 9.62341, 9.95328; h21.4989, 21.6238; and h33.0466, 33.4931, 33.8743. All ten are strictly inside a launched mission, with five occurrences of the same type in the first mission. There is no prelaunch damage, attrition, abort or cancellation.

Both arms have 72 aligned half-hour System and Stock bins through h36, six aircraft-hours of operation, terminal ready1, and zero backorder. `SystemResults.NDAM` in the rate arm records the ten event counts in their respective bins; all other System cells match the control. All Stock and ResultSummary cells match across arms. These tables and the explicit event log establish occurrence without asserting a positive consequence. The 12 raw artifacts from each arm are SHA-256 sealed locally and bound by `evidence-index.json`.

The author replay passed 91/91 checks. A separate standard-library read-only reviewer with no author-validator import or SIMLOX invocation passed 7750/7750 and returned GO for this bounded occurrence claim. Their results and reviewer code are sealed by `evidence-index.json`.

## Limits

This one seed and one high rate do not estimate a population frequency, prove an exponential distribution, or establish behavior at other rates. `PROB=0` means no attrition consequence is tested. DAMP/DAMRT mutual-exclusion rejection, item/system damage or repair, continuous missions, multiple aircraft, GUI visual behavior and cross-engine parity remain unverified.
