# Issue 18 monitor113: independent E05.var01 v1.0.1 prelaunch review

Heartbeat 2026-10-05T15:04:08.076Z. Original executor remains 4700-3 chat 01a0ed5b-dc75-74f3-a26c-23674dd997d6. Independent reviewer is the existing Mac mini monitor, not the case author. Reviewed remote AGENTS, README, architecture, semantic-baseline, roadmap, execution-plan-v2 and actual frozen package before this review. No native run, author-package edit or remote checker invocation by monitor.

## Verdict: NO_GO_PRELAUNCH — narrowed remaining findings

The v1.0.1 implementation materially improves monitor112's findings. Its ledger now checks remove/fit durations, printed backorder wait, repair due/pending status, ready/repair timelines and every half-hour report bin in the newly explicit bounded report scope. Author validator, ledger and shared parser bytes are now bound in contract/runner/invocation/closure. v1.0.0 and the prior NO-GO were preserved separately. These repairs do not constitute native acceptance; no child run exists.

Exact reviewed package at local commit 3d18f3d39d0171907a9c15924ddfa528508ba567:

- input 5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08
- contract b1e4d4bf04e2e3ed2aa67be73ce5780002b73375a6c0ee84bcb229b6c59b0ff7
- runner e1f79e3385cdc6532d50c052b32286d422c4a60b9e303ccbe4e3f98697c881eb
- validator 46379fac979b6b2014a1b3d772285eb2c9a734ee7e3caa9bf929e328dd434c69
- ledger 5a49b5695fe712b3e4b3bb353ec38f84aa59b1e7302bc0aba119f08349dcd98d
- shared parser 43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354

## R1 — blocking remaining physical/task lineage gaps

ledger_replay.py lines56–108 parse the demand's failed item, but critical failure scanning at line96 only counts the header; the adjacent raw `subitem failed` identities are not consumed. The ledger never tracks the installed aircraft item from the prior receipt and completed fit into the next failure/demand. Thus demand/removal/repair agreement alone does not prove the actually failed/installed item's continuity.

DIRP task start/work/completion IDs are parsed at lines70–74, but lines165–168 only match physical item/time, and line106 only compares overall completion counts. Per-repair lines196–212 match item finish/arrival but never join the corresponding DIRP task start/work/completion tuple. Fit start/wait/work/finish subtask IDs are similarly parsed without joining all same-task sequence-2 subtask identities. Complete task lineage is required by native_gate[3], not a new mechanism or broader model scope.

Two independent local in-memory negative checks used the sealed accepted E05 control log/report. Altering the first critical `subitem failed` ID1 to999, or the first item DIRP completion task1 to999, individually left **the entire ledger verdict and returned ledger unchanged**. The unmodified control intentionally fails six v101-specific checks because it is DIRPT1 without a shortage, so this is an invisibility/coverage demonstration, not a passing child counterexample or native acceptance. Raw controls were not rewritten; no native command was invoked. The mutated artifacts are diagnostic in-memory copies, not claimed native evidence.

Small repair: bind each critical-failure item's identity through actual demand/removal; maintain installed-item state from completed fit receipts and assert subsequent failed/demand identity plus the installed terminal ID. Join DIRP start/work/completion by task and physical item and require completion to the same task with the expected due time, or legitimate pending status at horizon. Join fit subtask identities through wait/restart/work/completion. Reject inconsistent or unobservable lineage explicitly. Add targeted negative checks where identities or task/subtask numbers change while counts/times remain unchanged; do not repair this by fixing expected demand times or IDs from the parent's run.

## R2 — remaining project dependency binding gap

The pinned shared tools/validate_native.py imports `from native_binding import verify as verify_binding` at line14. That repository module is loaded when the author validator imports shared, even though this case only calls shared normalization/roundtrip functions. native_binding.py is not among runner source pins or the validator's bound sources. Pin/seal the project-local transitive dependency and any further project-local imports it executes, or freeze a small inspected pure parser/roundtrip helper that does not import unrelated repository modules. Standard-library imports are not the requested dependency manifest scope. Verify exact actual bytes and before/after stability; preserve reviewed old versions.

## Scope and next step

Report gate now explicitly limits other report fields and requires all backorders to clear before36; those stated limits are acceptable for a bounded candidate. This review does not reimpose a GUI release gate or a general timing law. Runner's SSH0/sshd ancestry, serial mutex, protected GUI identity/start/session, unique runpath, exact roundtrip before calc, child-only cleanup and failure closures remain code observations, with live checks required immediately before any later independently approved launch.

Preserve this review and v1.0.1 exact bytes, apply R1/R2 in a fresh frozen package, do related authorized checks, then obtain fresh independent prelaunch GO. Do not run or publish reviewed v1.0.1. Do not immediately retry the same capacity-failed reviewer. If a repair remains blocked, keep E05 with recovery conditions and select eligible unoccupied planned work with accepted parent behavior/dependencies. Keep single original owner; do not change model/formal Goal status, create a replacement chat/Goal, or rerun accepted native parents. Overall Issue18 remains unfinished.
