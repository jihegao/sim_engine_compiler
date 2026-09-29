# C01 1.0.2: personnel specialty and quantity on B02 INSPECT

This case derives from the SHA-256-pinned [published B02 1.0.2 input](../B02-serial-preparation-v1.0.2/native-input.json). The old `preparation-resource-v1` C01 candidate uses the unpublished B01/B02 identity set and remains historical. Its resource fields and logs informed the new contract, but its input and run are not accepted parent evidence.

The [contract](contract.json) preserves B02's one aircraft, mission, schedule, notice, seed, horizon and 10+20-minute serial steps. It adds one two-person `P-CREW` demand to `INSPECT` (`SEQ=1`) through `SubTaskResource`; `SERVICE` remains unresourced. Four source variants change only `ResourceAllocation.RQTY`: crew capacity 2, 1, 0, or zero crew with two `P-OTHER` personnel. `ResourceAllocation.POINT=AIR_BASIC` matches the unchanged `Control.APID`. All resource types are `SPECIAL`.

The installed SIMLOX 2017 manual, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, defines `SubTaskResource`'s `(TID,SEQ,RID,QTY)` binding in PDF pp. 397–399, and `SPECIAL` integer personnel capacity in pp. 412–414. No alternative resource or random demand is declared.

`build.py --check` verifies all four inputs and exact parent diffs. Each native run has a fresh immutable ID and uses the authenticated session-0 SSH wrapper, host-wide mutex and original responsive GUI PID 13340 coexistence checks. The source-bound validator and independent read-only reviewer compare all raw variants against the frozen contract. The four accepted runs and bounded decision are recorded in the [dated evidence report](evidence-2026-09-29.md).
