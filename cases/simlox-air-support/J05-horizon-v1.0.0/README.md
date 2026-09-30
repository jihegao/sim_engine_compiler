# J05.var05: collection end and simulation period

This bounded A01-derived case changes `SYSTEM ResultCollection.RCEND` and `Control.SIMPE` independently. The [contract](contract.json) freezes four inputs and the [exact diffs](exact-diffs.json) show each child changes one behavior field plus the description. `rcend9` ends System time-series collection at hour 9 while the simulation remains 36 hours. `simpe48` extends the simulation to 48 hours while System and Stock collection still end at hour 36. The separate `simpe9` same-cutoff probe is a sealed native rejection, excluded from accepted behavior.

Fresh guarded session-0 SSH runs passed exact source roundtrip for all four 13-table inputs. Baseline, `rcend9`, and `simpe48` converted with zero errors and completed native calculation. `rcend9` has 18 half-hour System bins ending at 9, but its complete event log still records mission success and aircraft ready at 10; Stock remains 72 bins. `simpe48` has a native hour-48 log and result summary, including a day-two marker, while its System and Stock series each retain 72 half-hour bins ending at 36. `simpe9` was rejected by native errors #107 and #204 before simulation output; it cannot establish incomplete-mission cutoff behavior.

The [CLI scope sign-off](cli-scope-signoff-2026-10-01.md) records run IDs, raw SHA-256 seals, ledgers, independent review, and limitations. Raw runs remain ignored under `runs/`; the installed GUI PID 13340 was preserved.

## Reproduce on the pinned host

Run `python build.py` to check the frozen inputs. In an authenticated session-0 SSH shell, invoke [run_native_ssh.ps1](run_native_ssh.ps1) serially for `baseline`, `rcend9`, `simpe9`, and `simpe48`, each with a fresh run ID. The runner holds `Global\SimloxIssue18NativeQueue`, fingerprints the input and SIMLOX executable, and verifies GUI identity. A `simpe9` run is expected to stop after native conversion; preserve its closure and log as rejection evidence. Run `python validate.py` and `python review/independent_readonly.py` to replay the published run IDs. A changed cutoff needs a new contract and expected ledger.
