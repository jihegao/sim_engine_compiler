# D01 installed LRU and local repair, v1.0.0

Status: `native_behavior_accepted_cli_scope`, `reusable_published` for the restricted [dated sign-off](cli-scope-signoff-2026-09-29.md). This bounded variant derives from the accepted [D01 system-direct slice](../D01-system-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md). One LRU supplies the full system failure rate. A local spare supports system replacement, and the removed LRU enters one-hour local direct repair. The frozen [contract](contract.json) and [parent diff](parent-diff.json) state the source, intervention and native acceptance boundary.

The model still has one aircraft, three fixed mission opportunities and one simulation repetition. Stochastic failure time is observed in raw native events. The sealed `d01-lru-v100-ssh-20260929-01` run passed 64 author checks and independent read-only review. Its event ledger shows a local spare issued, the removed item repaired and stock restored.

Run `python build.py` to verify the frozen input. `python build.py --write` creates the input only when it is absent.
