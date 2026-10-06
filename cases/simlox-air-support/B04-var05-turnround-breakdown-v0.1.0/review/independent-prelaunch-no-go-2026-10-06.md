# Independent exact-file prelaunch review — NO_GO_PRELAUNCH

Reviewed on 2026-10-06. **Do not launch** `b04-var05-turnbreak-v010-ssh-20261006-01` with this validator. This is a review of the current file bytes, not a native result.

## Frozen identities

- Contract SHA-256: `5292459de185e04ef445ff89e4e20cb1c8d9148151f767340b59893d089d3020`.
- Child input SHA-256: `965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f`.
- Runner SHA-256: `d5e6624db4506c580eb4de56be5ecbf0c9397589d8d7cd1484756834dcf87a0a`.
- Behavior validator SHA-256: `a583083feafaa63272931708379b005d42eb7d7de992418f7979b8d862e0b015`.
- Prior contract-only review: `review/independent-contract-go-2026-10-06.md`, SHA-256 `e8b9a51252ba6620eced592ed369dbb8b984403b9f213bc679257eb699fc9f4a`.

## Findings

The source and contract remain coherent: one existing `MissionTurnround.TID` cell changes from null to `TURN-STEPS`; one `Tasks` row and two ordered `TaskBreakDown` rows define 1/6-hour INSPECT and 1/3-hour SERVICE subtasks. The accepted B04 parent and B02 prerequisite are pinned, and the current runner checks their 12 and 11 raw seals. The reported actual SSH PowerShell 5 `-PreflightOnly` passed with session-0 sshd ancestry, an absent target run, free global mutex, and the responding GUI PID 13340/session 1/start 1790590196826. The runner uses a hidden child process, checks GUI identity between stages, requires roundtrip before calculation, seals both successful and failed runs, and targets only its launched child on watchdog timeout. I found no separate GUI safety blocker in the current runner.

**Blocking validator gap:** the contract requires reconciliation of *all* 72 System and Stock half-hour rows and *all* ResultSummary fields. `validate_native_cli.py` checks only 7 of 11 summary fields, omitting `RSMTMF`, `RSMSTF`, `RSMSUF`, and `RSSTMF`. It checks selected System fields and four whole-horizon integrals, rather than each of 40 cells in each bin. For example, unexpected `NSYUA`, `NSYA`, `STACC`, or `NPSUC` values could pass. It checks only selected Stock zero fields, leaving columns such as `PNB`, `ROS`, `ROST`, `WT`, `WTT`, and `WTS` unconstrained. A report with altered unchecked cells can therefore return `GO_BOUNDED` despite violating the frozen full-ledger gate. The accepted parent report confirms these are actual emitted columns, not speculative names.

The event checks are useful but do not cure this gap: exact turnround subtask times and mission outcomes do not automatically validate every native report cell. The later planned independent replay is an additional publication control, but the frozen prelaunch gate requires the author's native validator to reject a divergent report before treating the run as accepted.

## Required correction before a new exact-file review

Keep the contract and input fixed. Extend the validator to check all 11 ResultSummary fields and every cell of all 72 SystemResults and StockTotalResults rows against explicit event-derived expectations or a justified parent comparison with exact declared differences, including null and interval-boundary semantics. Rehash the validator and runner's validator pin, repeat `-PreflightOnly`, then request a new exact-file review and approval bound to those revised bytes. Preserve this no-go memo as the historical prelaunch finding. No native process was started by this review, and no approval JSON was written.
