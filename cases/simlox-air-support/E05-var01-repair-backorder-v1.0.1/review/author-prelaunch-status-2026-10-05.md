# E05.var01 v1.0.1 author prelaunch status

Status: **awaiting fresh independent prelaunch GO**. No v1.0.1 native child has been launched, and its unique run directory is absent. This author check does not accept native behavior or override the independent v1.0.0 NO_GO.

The excluded v1.0.0 bytes and monitor112 review are preserved in local commit `b122009b6ff8d411e13c6363ff876e71815839f8`. The independent NO_GO file has SHA-256 `4217c5761e6ec84538748a127f612b794c4ac4a04099638cedb1f8564f5beab7`. The prior reviewer capacity failures remain in that package.

## Frozen v1.0.1 source identities

| Source | SHA-256 |
| --- | --- |
| native-input.json | `5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08` |
| contract.json | `b1e4d4bf04e2e3ed2aa67be73ce5780002b73375a6c0ee84bcb229b6c59b0ff7` |
| run_native_ssh.ps1 | `e1f79e3385cdc6532d50c052b32286d422c4a60b9e303ccbe4e3f98697c881eb` |
| validate_native.py | `46379fac979b6b2014a1b3d772285eb2c9a734ee7e3caa9bf929e328dd434c69` |
| ledger_replay.py | `5a49b5695fe712b3e4b3bb353ec38f84aa59b1e7302bc0aba119f08349dcd98d` |
| check_roundtrip.py | `c4366de43e097a83a43850157425cdaa1f5829f1de434cf450513af8ac127234` |
| shared tools/validate_native.py | `43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354` |

All 13 runner source pins match actual bytes. Contract pins the author validator, ledger and shared parser. The runner pins the contract and all three validators, and records runner and source hashes before and after a future run. The new run ID is `e05-var01-repair-backorder-v101-ssh-20261005-01`.

## Author checks performed without native execution

- Frozen builder and source checker pass under local Python and actual session-0 SSH PowerShell 5.1 file invocation. The child has exactly one authored cell change, ItemRepair record 1 `DIRPT` 1 to 13 hours; the accepted E05 parent input, signoff, closure and all 12 raw seals match.
- All Python files parse; PowerShell 5.1 parses the runner with zero errors. Session-0 SSH preflight observed exactly the protected GUI PID 13340, session 1, pinned start UTC `2026-09-28T10:09:56.8261381Z`, responding; no session-0 SIMLOX child; the host-wide mutex free; and no v1.0.1 run directory. These are transient observations and must be repeated immediately before any independently approved launch.
- The task-linked ledger parses accepted E05 and E02 control raw logs/reports without rerunning them. Their expected case-specific differences are rejected. Two opposite `NBO` bin mutations are caught separately at bins 20 and 21. Changing an issued physical ID to 999 adds receipt, held-ID, stock-membership and terminal failures.
- The revised ledger checks demand route, physical ID, removal, direct repair, stock membership, backorder printed wait, receipt, fit, SURP completion, ready/repair terminal states and every half-hour SystemResults/StockTotalResults bin. It requires all child backorders cleared before hour 36; a direct repair due after the horizon may remain pending and is enumerated. Any unsupported child behavior becomes a sealed failed diagnostic, not accepted evidence.

## Recovery gate

An independent reviewer must inspect **these exact v1.0.1 source bytes**, the physical ledger and per-bin assertions, and issue a fresh prelaunch GO. The v1.0.0 review applies only to excluded bytes. After GO, the executor must repeat live parent/source, ownership, GUI, session and mutex checks before using the unique run path. Any native result then needs an independent read-only replay and bounded scope review before an authorized PR or merge.
