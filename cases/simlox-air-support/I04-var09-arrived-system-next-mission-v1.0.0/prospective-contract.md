# I04.var09 bounded evidence classification — prospective contract

**Status:** awaiting independent GO_CONTRACT_ONLY. This document proposes a read-only classification of one already accepted SIMLOX run. It creates no model, run directory, SSH preflight, native command, converter output, or rerun of an accepted checker. The new classification ID is `i04-var09-arrived-system-next-mission-v100-20261008-01`; the accepted native run ID remains `i04-var03-idle-system-between-v101-ssh-20261008-01`. The proposed case path remains absent until independent contract review.

## Exact claim

The original I04.var03 v1.0.1 trace identifies aircraft `<TEACH-AIR-01,0>` at TEACH-UNIT, departing at h10.5, entering TEACH-UNIT-2 at h11, becoming ready there, and joining the later TEACH-GROUP mission at h19. That mission starts h20, runs the task h20.5–21.5, succeeds at h22, and the same observed numeric ID becomes ready at the target after turnround. This supports only the “arrival then later mission” branch of catalog I04.var09. It does not show a second transfer after arrival, immediate task assignment on arrival, a general identity rule, or the whole variant.

The [separate I04.var07 readiness NO_GO](../i04-var07-author-contract-readiness-no-go-20261008.md) remains unchanged. Its same-time scheduling gap is not used as evidence here.

## Evidence and custody

Root’s read-only selection receipt is 9,507 bytes/SHA-256 `f198bdf3ef4e4778ac2dca5d87d185afb74b94f214aeebf5da4cef800a156192`. The accepted parent index is 176,439 bytes/SHA-256 `09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff`: 401 indexed source files, 153 mandatory raw originals and 15 separate mandatory preflight originals (168 total). The selection additionally checked 403 current disk/Git source pairs. The accepted prelaunch manifest is 161,922 bytes/SHA-256 `d05541613248279a5620349ade72bcaf80b12f3be042b470694f45b6efa690f3`, with 456 source roles. The new reader must rehash those closed identities, including mandatory local-only private originals without publishing their bytes. It may not import or execute the old validators.

The accepted original `model.log` is 8,223 bytes/SHA-256 `ab19c3cbc0214b8e72b57d6139d94166beb99f1afa034e07de393693d1079901`, with 118 physical lines, 104 timed records and one transfer out/in. The original report is 103,970 bytes/SHA-256 `72a5bd7270f5b3b27736df43c146a56f850990abf6a8e964aa7bae430ffc93b5`. The prior independent GO_POSTRUN_BOUNDED memo is 4,369 bytes/SHA-256 `d5b7ea964e65ddb57d248562dab82f53bce565f6d0ac7a161c4eccc5b8ebf7c7`: it already accepted all 4,044 cells of this original run. The proposed classifier adds selected-cell and identity-chain checks; it must not claim a fresh full-report replay.

The historical catalog 496-entry local CRLF archive, Git LF archive, and former prelaunch live alias are exact separate identities. The 497-entry archives and current 498-entry local/Git files are also distinct byte identities. A future sealed replay must verify historical typed prefix, metadata and unique publication IDs while allowing a later authorized append; it must never infer byte equality from normalized content.

## New read-only classification test

Parse all 118 lines, including continuations, with a closed grammar and exact mission IDs. Track both observed numeric IDs at each event microstep. ID 0 is ready under source roster ownership, allocated to the first mission h7–10, ready again at source h10, in transit without unit ownership h10.5–11, ready under target ownership h11–19, allocated to later mission ID `<BASIC-MISSION,TEACH-GROUP,0,0,1>` h19–22, and ready at target after h22. Track mission assignment, flight, task activity and turnround separately from unit roster ownership. Require no allocation during transit, no duplicate source/target ownership, and exactly balanced departure/arrival and mission transitions. ID 1 remains separately identified; no third aircraft or outside-person pool is inferred.

Selected original SystemResults bins must match the accepted raw report: [10.5,11) NSYA/NSYRY=1; [11,11.5) both=2; [19,19.5) NSYA=2, NSYMA=2, NSYMR=2, NSYRY=0; [20,20.5) NSYMO=2; [22,22.5) NSYRY=2. Parse the native report strictly (one declared trailing-comma repair only, duplicate keys/nonfinite/bool-as-number/extra structures rejected). The entire report remains byte-pinned to the prior 4,044-cell independent verdict.

The sealed reader checks original SHA/size and custody first. A separate in-memory negative harness calls the new semantic parser and ledger on private clones with the outer byte-pin layer deliberately set aside; this proves the identity/time/ownership predicates reject for their own reasons. No accepted original is changed.

Before source freeze, meaningful in-memory mutations must reject a missing/extra transfer edge, wrong or duplicated numeric ID, wrong time/unit/mission, allocation while in transit, missing return/ready, duplicate ownership, unknown full-log lines or continuation, selected-cell change after synthetic reseal, wrong numeric type, duplicate JSON key, and extra report structure. These tests must not invoke SIMLOX or accepted checkers.

## Decision path

Independent GO_CONTRACT_ONLY is required before creating the case package or executable classifier. A later classifier must run read-only on the original accepted evidence and receive its own independent bounded review. Any catalog entry must state integer `new_native_runs: 0` and `accepted_parent_runs_repeated: 0` and clearly identify reclassification of existing evidence. Root retains catalog and Git publication ownership. No new native run is authorized by this contract.
