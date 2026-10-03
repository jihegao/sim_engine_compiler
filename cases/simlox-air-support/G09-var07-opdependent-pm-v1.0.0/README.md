# G09.var07 v1.0.0 excluded disabled-PM diagnostic

The frozen [contract](contract.json) tested whether BASIC system USERT 0.5 versus 1 shifts a system OPHOURS1.5 PM task. Both arms inherited `Control.ENPM=N` from accepted G09.var04. The two guarded session-0 SSH runs converted with zero errors and reviewed warning #108, roundtripped all 30 populated tables, and produced 13 locally sealed raw files each. Neither arm scheduled any PM: every 72-bin SystemResults row has `NPMS=NPMT=0`, violating the predeclared first-PM timing gate.

This v1.0.0 pair is **diagnostic, not published as PM behavior**. The [diagnostic evidence index](diagnostic-evidence.json) preserves the frozen input, source and raw file SHA-256 seals. [G09.var07 v1.0.1](../G09-var07-opdependent-pm-v1.0.1/README.md) enables `Control.ENPM=Y` in both arms under a new contract and run IDs. The v1.0.0 result supports only that PM was disabled for these inputs, not a statement about usage-dependent PM timing.
