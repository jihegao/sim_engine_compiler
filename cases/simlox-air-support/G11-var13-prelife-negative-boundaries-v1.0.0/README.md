# G11.var13: three negative prelife input boundaries

This bounded case derives three malformed inputs from separately accepted G11 parents. The frozen [contract](contract.json), [builder](build.py), and [exact table diff](exact-diff.json) pin each one-row or one-node change. Installed manual physical page 469 prohibits multiple blank `PrelifeData.QTY` rows for one prelife identifier and a quantity sum above deployed materiel count. Pages 474–475 require prelife structure through the physical intermediate materiel path.

| Arm | Single semantic change from accepted parent | Installed converter observation |
| --- | --- | --- |
| `two-blank-qty` | AGE60 `QTY=1` becomes blank while AGE120 is already blank | Error #312, more than one blank quantity row for `PL-SYS` |
| `overallocated-qty` | AGE120 `QTY=2` becomes 3; explicit total 5 exceeds four deployed systems | Error #311, materiel quantity less than prelife quantity |
| `missing-middle` | Remove `PL-POS` and connect `PL-LRU` directly to `PL-SYS` while physical `SYS→POS→LRU` remains | Error #414, sub-prelife materiel is not part of mother-prelife materiel |

All three guarded session-0 SSH runs imported and exported the input with every populated authored table row preserved. Calculation returned process exit code 0 but reported exactly one converter error and produced only a 4-byte `.sxo`; no JSON report was generated. The quantity arms each also reported warnings #108/#126 inherited from their accepted G11.var05 parents; the missing-middle arm reported #108. The wrapper intentionally exited nonzero because a valid simulation output was absent. Each run sealed its invocation, step record and nine raw files in the ignored local `runs/` directory, preserved GUI PID13340, and restored the Prelife Log option to `NO`.

Run `python build.py`, `python describe_diff.py`, and `python validate_rejection.py` to verify the frozen sources and local evidence. The [evidence index](evidence-index.json) records source, parent and raw hashes. The [author replay](author-validation.json) and separate [independent review](review/independent-rejection-2026-10-03.json) check the bounded rejection evidence without treating a wrapper exit code alone as proof. The [CLI sign-off](cli-scope-signoff-2026-10-03.md) states the acceptance limits.

These are three installed converter outcomes for three specific malformed inputs. They do not establish arbitrary input validation, valid simulation behavior, GUI visuals, or cross-engine parity.
