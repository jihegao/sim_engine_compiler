# E05 local LRU repair and second issue, v1.0.0

Status: `native_behavior_accepted_cli_scope`, `reusable_published` for the restricted [dated sign-off](cli-scope-signoff-2026-09-29.md). This case derives from [accepted E01](../E01-local-spare-explicit-replacement-v1.0.0/cli-scope-signoff-2026-09-29.md). It retains one local spare, explicit 10/20-minute replacement steps and one-hour local direct item repair. The only behavioral intervention raises both matching traditional OPHOURS failure rates from 300000 to 450000 per million. The [contract](contract.json) and [parent diff](parent-diff.json) freeze the acceptance boundary.

The sealed `e05-v100-ssh-20260929-01` run observed three complete repair/restock/issue cycles. The second demand issued the first repaired LRU and the third issued the second repaired LRU. Author replay passed 79 checks and independent read-only review passed with no differences.

Run `python build.py` to verify the frozen input. `python build.py --write` creates it only when absent.
