# C05.var03 sealed single-arm counterexample

This package classifies an existing C05.var03 v1.0.2 **crew-arm** native trace. It adds no native run. The original two-arm positive gate remains **NO_GO**; its radio arm was not started.

In the sealed crew trace, both base aircraft are assigned at h7 and each briefly books one MISSION-CREW. Both bookings are released at h7 during reconfiguration. Configured A0 and B1 then launch at h8 and succeed at h10 with mission crew quantity zero. Every half-hour ResourceResults bin has zero held/used/waiting crew; all 5,210 cells in the six native report tables are independently reconciled. The result is specific to this source, event trace and CLI version. It does not establish a general configuration resource inheritance rule.

The h7 demand text prints position suffix 0 for both item types. That suffix is not a physical aircraft owner. The fit task and configured aircraft events separately identify base aircraft 0 and 1. Opening A/B item IDs and stock take edges are recorded, but a serial item-to-aircraft continuity claim is outside the evidence.

The read-only [author validation](author-validation.json) passes 6,023/6,023; the separate [independent verdict](review/independent-verdict.json) accepts this narrow retrospective claim and preserves the original pair rejection. Raw files remain local and ignored. The repository's `../publication-index-v1.json` is authoritative for publication status.

From this package directory, with the local sealed v1.0.2 run and accepted parents present, reproduce the read-only checks using the bundled runtime:

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' check_reclassification.py
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' self_check.py
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' make_evidence_index.py
```

The sealed input, event log and report are in `../C05-var03-config-resource-v1.0.2/runs/c05-var03-v102-crew-ssh-20261007-01/`; their local raw seals appear in [evidence-index.json](evidence-index.json). The index is a byte map, not a replacement for the ignored native raw. Any different input or new native test requires a fresh versioned contract, unique run IDs, and independent prelaunch review. It cannot repair the original pair's frozen NO_GO retroactively.
