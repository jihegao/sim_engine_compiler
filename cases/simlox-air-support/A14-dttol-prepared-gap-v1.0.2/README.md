# A14 typed DTTOL abort-hypothesis diagnostic (v1.0.2)

**Decision: NO-GO for the frozen abort hypothesis.** This version separated aircraft types: SUPPORT uses three failure-prone TEACH-AIR-01 instances and EXECUTE uses one nonfailing EXEC-AIR-01. The accepted A11 MissionSystem schema constrains each mission to its type. Its five guarded native runs reproduced the same SUPPORT failure at hour 9.8829, half-hour prepared-replacement gap ending 10.3829, and healthy EXECUTE aircraft. That fixed the stochastic comparability problem in v1.0.1. But the contract's prediction that DTTOL=0 or 0.49 would *abort* EXECUTE was false: both suspended and resumed, and all five EXECUTE missions succeeded at 11.9.

The accepted A05 prepared-spare parent input SHA-256 is b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d. The accepted A11 schema donor input SHA-256 is 4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213. Exact-diff SHA-256 is c9b1d8c8328b613d7720d7e640b892865ead558058876a8cef8bad7edd4870d7. The frozen contract and five immutable inputs preceded execution. All runs completed exact 17/18-table business-row roundtrip, zero converter errors and classified warnings #108/#126 under session-0 SSH, the host-wide mutex and GUI PID 13340 identity guard.

| Variant | DTTOL hours | Immutable run ID | Closure SHA-256 |
| --- | ---: | --- | --- |
| Control | no row | a14-dttol-control-v102-20261001-01 | debaa630411396a68d82fb23c4502871666e4cdd0bbe827a4327629cdef887a0 |
| Zero | 0 | a14-dttol-zero-v102-20261001-01 | 0f6e39915069ce6e4776cd0aa6a3579a31c48703f8b94b90976d940d5f892228 |
| Below | 0.49 | a14-dttol-below-v102-20261001-01 | 79f3baaaedb434cdedcd73f9f7fb9be1e7819b3e4139b4e3a6ff9494ac9d555a |
| Edge | 0.5 | a14-dttol-edge-v102-20261001-01 | 1678f42e5010c0404be032d4fe841b19f31c1bbf45df8275d25d231c47c07036 |
| Above | 0.51 | a14-dttol-above-v102-20261001-01 | 3f160f88b23177fc852bcdf2075905d9907e4874ff8bddb4095cc94d4121ebcf |

The raw logs revealed a suspend/resume threshold: EXECUTE suspends at 9.8829 when DTTOL=0, at 10.3729 when DTTOL=0.49, at the 10.3829 resume instant when DTTOL=0.5, and not during the gap when DTTOL=0.51. These are diagnostic observations, not retroactive acceptance of the false contract. Raw outputs remain in ignored local runs/. The separately frozen [v1.0.3 replay](../A14-dttol-prepared-gap-v1.0.3/README.md) tests this revised behavior with fresh native IDs.
