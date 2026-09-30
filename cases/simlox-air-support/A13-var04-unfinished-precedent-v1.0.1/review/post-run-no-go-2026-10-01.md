# A13.var04 unfinished precedent v1.0.1 — independent post-run NO-GO

Read-only review of two sealed native diagnostics. The frozen v1.0.1 contract required zero conversion errors, valid results, and a 22-bin runtime comparison. Neither run reached simulation behavior, so that acceptance gate fails.

## Sealed paired evidence

- Control run `a13-var04-unfinished-control-v101-20261001-01`, closure SHA-256 `f994c57b4bb5235b6eb3e8832b35d71499aa47c4d0921630a4f73aed89d69608`; dependency run `a13-var04-unfinished-dependency-v101-20261001-01`, closure SHA-256 `550f354418f1a2139dbb45fd1058a16982aaaded4ca97203276574d9d6e14586`.
- I independently recomputed each invocation hash and all nine raw-file byte counts/SHA-256 values in its closure. In both, before/after source hashes match, the copied input hash matches its frozen source, and invocation records session-0 SSH with `sshd.exe` ancestry, `Global\SimloxIssue18NativeQueue`, and GUI PID 13340/session 1. All four recorded steps—import, export, calc, source roundtrip—have exit code zero and preserved-GUI flags. No JSON-report step was scheduled after failed conversion.
- I independently compared populated source rows/columns with the raw native export: **13/13 control** and **14/14 dependency** tables match exactly. The source checker also reports pass, but this source-row result does not establish conversion or simulation behavior.
- Both `run.log` files report one `Operations` error: `#204 Some missions may not return before simulation period ends`. Each also reports only warnings #108 and #126, then `Input conversion completed. Errors: 1, Warnings: 2, Notes: 0`. Each `.sxo` is four bytes; neither run has `model.log`, `report-raw.json`, or 22-bin ledgers. A zero calc process exit code therefore does not imply a valid run.

**Decision: NO-GO for the frozen v1.0.1 unfinished-precedent behavior claim.** The evidence supports only a paired converter rejection for these hour-11 inputs. It shows no FOLLOW assignment, waiting, launch, cancellation, or terminal aircraft state. The rejected v1.0.0 static source remains separately excluded.
