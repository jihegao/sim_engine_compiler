# G11.var13 negative prelife input CLI sign-off — 2026-10-03

**GO for three bounded installed-converter rejections.** The accepted parent input and native closure for each arm are pinned in the [contract](contract.json). The authored delta is exactly two changed tables for each quantity arm (`PrelifeData`, `ProblemDescription`) and four for the missing-middle arm (`Prelife`, `PrelifeData`, `PrelifeStructure`, `ProblemDescription`). Other source tables remain equal to their corresponding accepted parent. Installed manual physical pages 469 and 474–475 describe the violated quantity and intermediate-path rules.

| Arm | Native `run.log` converter result | Import/export | Simulation output |
| --- | --- | --- | --- |
| `two-blank-qty` | Errors 1: #312; warnings #108/#126; notes 0 | 20 populated authored tables preserved | 4-byte SXO; no report |
| `overallocated-qty` | Errors 1: #311; warnings #108/#126; notes 0 | 20 populated authored tables preserved | 4-byte SXO; no report |
| `missing-middle` | Errors 1: #414; warning #108; notes 0 | 23 populated authored tables preserved | 4-byte SXO; no report |

The three serial session-0 SSH runs used the host mutex, preserved responsive GUI PID13340, and restored the Prelife Log option `NO`. Native calc returned exit code 0, while the wrapper reported missing valid SXO and exited 1. The exact converter diagnostics, absent JSON reports, successful import/export row checks, and sealed raw files establish rejection; the wrapper exit alone does not. The [author replay](author-validation.json) passes 112/112 checks and the separate [independent replay](review/independent-rejection-2026-10-03.json) passes 229/229. The [evidence index](evidence-index.json), SHA-256 `5880a06285c16ced8aa92598f02f644561ad5ae87d0ce72adaeb88235d4e2029`, seals 27 local raw files across the three runs.

This sign-off applies only to the three frozen malformed inputs and the installed executable fingerprint. No mission or report outcome is accepted from these inputs. Other invalid combinations, GUI visual behavior, and cross-engine parity remain unverified.
