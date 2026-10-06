# Independent exact-file prelaunch review — GO_PRELAUNCH

Reviewed 2026-10-06. Approval applies to **one** run, `b04-var05-turnbreak-v010-ssh-20261006-01`, and the exact bytes in `independent-prelaunch-go.json`. The earlier two no-go memos remain intact as revision history. This is approval to test the frozen hypothesis, not an acceptance of any native outcome.

## Source and guard checks

- Contract SHA-256 `5292459de185e04ef445ff89e4e20cb1c8d9148151f767340b59893d089d3020`; input `965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f`.
- Runner SHA-256 `8dc0600ffcb5979bc1e855c93b5d3528eb0df838f85ca409bd58e1b38c931be4`; validator `1d56c6c0338866aa92d4124146eb2fbe0d0307ebd3e41c7031b9ee377d988325`; expected ledger delta `5659de210fd4f9eca999b616615eb62f124ea0a8ff789f1718549a7ae0b239dc`.
- The independent source-diff check found exactly one existing `MissionTurnround.TID` cell changed, 17 cells added across one `Tasks` row and two ordered `TaskBreakDown` rows, and none removed. Python source syntax parses; the runner pins builder, diff and roundtrip checkers, shared parser, executable, installed manual and dictionary, parent, prerequisite, and the revised validator/delta.
- Accepted B04 closure: 12/12 local raw SHA and size seals match; B02 prerequisite: 11/11 match. Accepted B04 report SHA-256 is `ea429a8c563f50256ca24168e8ae103222e5fe01918fbb52c40c6adf64a66897`.
- The target run directory is absent. The actual SSH PowerShell 5 `-PreflightOnly` was reported to pass in session 0 with sshd ancestry, free `Global\SimloxIssue18NativeQueue`, and responding GUI PID 13340/session 1/start 1790590196826. Runner inspection confirms a hidden native child, GUI assertions before and after stages, a watchdog that targets only its launched child, roundtrip before calculation, and source/raw failure sealing.

## Strict native gate reviewed

The revised validator requires the two mission notice/creation/activation identities, the second preassignment, both mission outcomes, both post-turnround physical `System arrives` events, and preparation and turnround SEQ1/SEQ2 starts, performance, completions, and planned durations. I tested its regex source against the accepted B04 log: it matches two notices, two created, two activated, two arrivals, eight preparation/turnround lifecycle lines, and all 18 parent subtask lifecycle lines, including the existing preparation steps. The candidate must add the expected turnround SEQ1/SEQ2 lines; this remains a native observation gate.

The validator now compares **all** 11 ResultSummary, 72×40 SystemResults, and 72×16 StockTotalResults cells with the accepted parent after a frozen 21-cell patch across System row indexes 48, 49, 50, 53, 54, and 55. I checked each patched field against the parent rows. The proposed h24–24.5 preparation, h24.5–24.75 reservation, h24.75–26.75 flight, and h26.75–27.25 turnround yield the declared half-bin values. Accepted B04.var01 quarter-hour evidence independently supports half-bin flight/turnround values and `NPSTA`/`NPSUC` placement; accepted B04 parent row 42 shows `NSYMR` during prepared prelaunch waiting. All unlisted fields must remain exactly equal to the parent. A differing native report must be sealed as a diagnostic, with no post hoc gate relaxation.

## Limit

This authorizes one CLI run only. It does not establish the outcome, arbitrary turnround task semantics, GUI behavior, resource contention, or any broader B04.var05 claim. A separate independent read-only replay of the sealed native evidence is still required before publication.
