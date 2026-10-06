# C05.var02 independent contract-only review

**Decision: GO_CONTRACT_ONLY** for the frozen `contract.json` SHA-256 `1028e32013b7f3b655254d10c0f2cdb40529a73517326e5b5929e32639d2a7de`. This permits a separate read-only replay of already accepted evidence. It does not approve a new native run or establish a new behavioral discovery.

## Source and provenance

- The current branch and HEAD match the contract's branch/base `4edeecbf4ce287c1d892ca6781530c6a42862db5`. Its exact PR-title search is explicitly `not_verified`; no absence-of-PR claim is needed for this contract decision.
- I independently recomputed **122** literal byte/size pin checks with zero mismatches: 16 published C05.var02 source files and 17 direct C05 capacity-two parent source files against separate local/Git identities; A03/C01 prerequisite pins; both C05.var02 invocation/closure chains and **24** child raw seals; and the direct C05 parent invocation/closure chain and **12** parent raw seals. The installed manual PDF independently hashes to the contract's `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
- Direct source comparison shows the two C05.var02 arms each differ from the accepted capacity-two parent only in `ProblemDescription`, `Resource`, `ResourceAllocation`, and `MissionResource`. The radio pair differs only in `ProblemDescription` and the `AIR_BASIC`/`MISSION-RADIO`/`BASE-01` `RQTY` cell **2→0**; both retain crew capacity two and one required crew plus one required radio per aircraft. The source keeps the fixed two-hour mission and seed.

## Feasibility of frozen gates

- Original guarded invocations record SSH session 0, global native mutex, protected GUI PID 13340/session 1/exact start, five completed GUI-preserved stages, and unchanged before/after source hashes. These are historical provenance records, not a fresh GUI observation.
- The sealed logs show two typed crew and radio availability successes, two per-aircraft bookings of both types, two aircraft allocations, h8 launch, h10 completion, and four unit releases when radio capacity is two. With radio capacity zero, each crew test succeeds but each radio test fails; neither resource type books, no aircraft allocates or launches, and the mission cancels h8.33333. Both aircraft are ready terminal. This supports **per-system** all-required-types-before-booking and must remain separate from C05.var01's observed partial *formation* assignment.
- Each report has the declared six-table grid of **5,210 cells**: 1/11/2,880/1,152/1,152/14. Direct cell comparison gives the predeclared 2-vs-0 changed counts **1/4/26/0/222/5**, with StockTotalResults fully equal. The contract's full-cell, time-bin and physical-ledger replay is therefore feasible from the preserved raw evidence.

## Limit

The already published `C05.two_mission_resource_types.1.0.0` package contains this two-arm native result. A C05.var02 publication may only map that result to the catalog variant; it must say it overlaps the accepted package and adds no new run or behavior. The radio-one asymmetry, extra resource types or ground preparation, other seeds, catalog one-hour form, general ordering rule, GUI-specific behavior, and cross-engine parity are outside the evidence. An independent read-only checker and separate publication gate remain required.
