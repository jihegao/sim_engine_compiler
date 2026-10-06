# B04.var03 next-mission notice during turnround v0.1.0

This package classifies one already accepted native run for the catalog's B04.var03 question. It creates no new SIMLOX input or run. The source is the [B04.var05 linked-turnround package](../B04-var05-turnround-breakdown-v0.1.0/README.md), whose frozen input and native raw evidence are referenced by SHA-256 in the [contract](contract.json).

In that one-aircraft, two-mission run, the first mission succeeds and turnround starts at h23.5. The next mission is ordered, created, activated and preassigned the same aircraft at h23.75, while the second turnround subtask is still performing. The turnround ends and the aircraft physically arrives at h24; only then does the second mission allocate that aircraft and begin preparation. Preparation ends h24.5, launch occurs h24.75 and success h26.75.

Run `python check_reclassification.py` for a read-only source, raw-seal, event and accepted full-ledger check. The independent checker and verdict in `review/` replay this bounded claim separately. The evidence index points to the original run directory; there is no new `runs/` directory or duplicate accepted execution.

This is retrospective evidence reuse for one fixed-seed input. It has no matched later-notice control and does not establish arbitrary notice lead times, same-time internal priority, contention, GUI visual behavior, cross-engine parity, or full Issue #18 completion.
