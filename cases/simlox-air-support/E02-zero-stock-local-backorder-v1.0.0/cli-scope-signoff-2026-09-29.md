# E02 zero local stock and repair-served backorder: CLI scope sign-off (2026-09-29)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one empty local stock point whose first system replacement demand is filled by repair of the removed LRU. This case does not accept remote supply, multiple simultaneous demands, FIFO ordering, reorder, resource contention or PM.

## Frozen source and execution

This case derives from accepted E01 input SHA-256 `84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931`, with accepted E05 repair/reissue as a prerequisite. The [parent diff](parent-diff.json) changes only `ProblemDescription` and `StockAllocation`, setting the local repairable LRU nominal stock from one to zero. E02 input SHA-256 is `12ef9bfd6ab88f7a796733bca0a283bfbf4e0be525eba02f3e98122212ac49dd`; predeclared [contract](contract.json) SHA-256 is `2b22e7a44d2aa1079ac03dc0b7b9c693645b2ac8dc9e78157708129c3bf8040b`. Installed SIMLOX executable SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.

Native run `e02-v100-ssh-20260929-01` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` mutex and active GUI PID 13340 guard. Import, export, calculation and report export exited zero; 20 row-containing source tables, including three all-null placeholders, roundtripped identically. Conversion had zero errors and only logging warning 108. Sealed invocation SHA-256 is `a4a6700d60f9d351fe438772750c8d6faeffd97f801aa2c97eb572abf6db22f7`; closure SHA-256 is `a8ec55f67c710be700cb4dc3663c7f79041d69c2021edb9924c1d0daddda04ef`. Raw evidence stays in the ignored local `runs/e02-v100-ssh-20260929-01/` directory.

## Observed material and waiting chain

At time zero the stock level is zero. The installed LRU instance 0 fails critically at 9.8829 hours, aborting the first mission. System SURP demands that same failed item at 10 and creates one backorder. The explicit 10-minute REMOVE runs from 10 to 10.1667, when instance 0 reaches local ItemRepair. The one-hour repair completes at 11.1667. The returned **same instance 0** clears the backorder after 1.16667 hours and is received by the waiting system; it does not enter stock. Physical 20-minute REPLACE fit runs from 11.1667 to 11.5, when the aircraft becomes ready. Later missions ending at 22 and 34 succeed.

The native log labels the fit task `started` at 10.1667 but immediately logs `wait for subitem`. Its `starts performing` event occurs only at 11.1667, after the repaired item is received. The contract's wait to begin REPLACE is interpreted as physical fit work, which the native event sequence verifies.

Raw event log SHA-256 is `bdea346172a799f2c4c1630fe5f9f132dda6d5f4f6c439fc024ed329bc09dd0c`; raw JSON report SHA-256 is `b5b83fbdc877eac297ba8a7492bdcdb162c6eeaab64901eacb16a3daa5cacf3e`. The report has 72 aligned half-hour system and stock intervals, one failure, one completed repair, one demand, a backorder occupancy area of 1.16667 hours, terminal ready aircraft and no terminal backorder. Its mission success fraction remains two-thirds, as in E01. Relative to E01, system readiness moves from 10.5 to 11.5 and the 36-hour aircraft-availability integral falls by one hour. Item identity and exact transition times come from the event log; the report gives aggregate intervals and rounds times differently.

## Review and limits

The [author replay](review/author-native-validation-2026-09-29.json) passed 70 source-bound checks with no differences. Its source SHA-256 is `189e514d93139d7180de6be1ab52153997d03c74ed5b0271da317e777f3fd6c4`, and its report SHA-256 is `9274d885151dd06ecf1ca823c533fcd7a745f69609e39e4e37662e32d299a616`. A separate reviewer performed [static prelaunch review](review/static-review-2026-09-29.md) and [independent read-only native replay](review/independent-native-review-2026-09-29.json), with no differences. The independent report SHA-256 is `fbcc2270e7f3c8987d9497c3df6ae6f9989733db59ebb001a7d9410bb7e18f3d`. The reviewer checked frozen inputs, the two-table delta, sealed raw hashes, SSH/GUI records, same-item backorder clearance and the E01 control.

The seed does not prescribe the exact stochastic failure time on other executables. GUI visual content was not sampled.
