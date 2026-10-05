# E05.var01 v1.0.2 author prelaunch status

Status: **contract candidate awaiting fresh independent prelaunch GO**. No v1.0.2 native child has started and its unique run directory is absent. This author assessment does not accept behavior or override monitor113's NO_GO on v1.0.1.

The exact excluded v1.0.0 package and monitor112 review remain in local commit `b122009b6ff8d411e13c6363ff876e71815839f8`. Exact excluded v1.0.1 source bytes remain in commit `3d18f3d39d0171907a9c15924ddfa528508ba567`; monitor113 review SHA-256 `56c8d1377820ca3e5493ae3aac8622448cfc2e3c7211c90c54c8acaf7d9b044f` was separately copied to that package in commit `2b1cc907cf2c6361839310a44c196d7e1239d0df`.

## Frozen v1.0.2 source identities

| Source | SHA-256 |
| --- | --- |
| native-input.json | `5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08` |
| contract.json | `6dca432a09bc441544f21c69aa9f7232bff1c5ebdb430145a9de04e32a4b6d94` |
| run_native_ssh.ps1 | `0f53dfe97c06899f3ad250a33336db38bc08d57b447a1a7bdf14fa4a452e8b8e` |
| validate_native.py | `80c61f5dd59c9ac4d969570602170d5344aa6b77ce7140a74d02790c1a120ee3` |
| ledger_replay.py | `3bf2e3c711b02c5ba32af47bd539d44b938a0dc030185e4afc944e5bfc934e57` |
| check_roundtrip.py | `98a927e6f4cb57d405ec2eb9a3ed672a09977300e44411279893795b9d467b4c` |
| shared tools/validate_native.py | `43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354` |
| transitive tools/native_binding.py | `d7cb8cdb670d6ac24536254904d9ac527bee1cfa1d9954dca9bd6a7d9ca0c28a` |

All 14 runner source pins match actual local bytes; contract pins author validator, ledger, shared parser and its only project-local transitive import, `native_binding.py`. The runner records all of these before and after a future run. New run ID: `e05-var01-repair-backorder-v102-ssh-20261005-01`.

## R1 correction and observability limit

The ledger now binds the `critical random failure added` adjacent subitem ID to the failed-system arrival, demand and removed item. It joins each DIRP task start/work/subtask completion and physical return by task/subtask/item and due time; each fit wait/restart/work/completion uses one subtask identity within its SURP task. It records the terminal fit receipt ID separately from terminal ready/repair state.

The accepted E05 raw log itself exposes a physical ID gap: stock ID0 is issued at line 45 and its fit completes at line 67, but the next critical failed installed item is ID2 at line 96. No intervening CLI event maps ID0 to ID2; the aggregate native report does not provide an installed physical-item map. The revised contract therefore **does not claim** post-fit installed physical ID, cross-cycle ID continuity or terminal installed physical ID. It verifies the two observable identity chains and the temporal fit-to-next-failure order. Independent review must decide whether this narrower boundary is sufficient for a reusable E05.var01 backorder contrast; if it is not, preserve v1.0.2 as a diagnostic and seek an independently justified observation path before running.

## Author checks without native execution

- Frozen builder/source checker pass locally and through the actual session-0 SSH PowerShell 5.1 path. The sole authored input change remains ItemRepair record 1 DIRPT 1 to 13 hours; accepted E05 parent input/signoff/closure and all 12 raw seals match.
- Python AST and PowerShell 5.1 parsing pass. The direct validator file invocation over SSH reached its expected missing-run failure without creating a run directory. A separate `runpy` harness initially omitted the case directory from `sys.path`; after correcting the harness, it loaded the pinned shared parser and `native_binding` module.
- Accepted E05 and E02 raw controls parse in memory without native reruns. They fail only expected case-specific v1.0.2 predicates (6 and 5 respectively). In-memory mutations independently add failures for the critical subitem ID, DIRP completion task ID, fit completion subtask ID, fit-wait subtask ID, and each of two offsetting NBO-bin errors. Raw controls were not modified.
- Transient session-0 SSH observation found protected GUI PID 13340/session 1/start `2026-09-28T10:09:56.8261381Z` responding, one total SIMLOX process, no session-0 child, free `Global\SimloxIssue18NativeQueue` mutex and absent v1.0.2 run directory. Repeat all live checks immediately before any independently approved launch.

## Recovery gate

Obtain a fresh independent prelaunch review of these exact v1.0.2 bytes, especially the narrowed installed-ID scope, task lineage and transitive import binding. No native run, PR, merge or behavior acceptance can follow a NO_GO. After a GO, perform fresh live source, parent, ownership, GUI, SSH, mutex and unique-path checks. A completed native run still requires an independent read-only replay and bounded scope review before publication.
