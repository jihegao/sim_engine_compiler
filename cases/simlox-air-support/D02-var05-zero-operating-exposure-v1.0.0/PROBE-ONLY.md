# D02.var05 first no-profile probe: rejected input

This candidate removed all three `OperationProfile` rows from the accepted D02.var01 model but left the unit's `Operations.PRID=BASIC-SCHEDULE` assignment. The sealed local run `d02-var05-zero-op-v100-ssh-20260930-01` imported and exported, then native conversion reported error #77, `Unknown operational profile (PRID): BASIC-SCHEDULE`. Calc returned zero but produced only a 4-byte unusable SXO. Closure SHA-256: `0afdc95a96070b60af4effe18a2246609e087bf7c21a024ecf6c36541250e2b9`. This input is **not published** as zero-exposure behavior; the raw run is retained under ignored `runs/`.

The corrected experiment and its accepted scope are in [D02.var05 v1.0.2](../D02-var05-zero-operating-exposure-v1.0.2/README.md).
