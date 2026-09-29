# E01 one local spare with explicit replacement, v1.0.0

Status: `native_behavior_accepted_cli_scope`, `reusable_published` for the restricted [dated sign-off](cli-scope-signoff-2026-09-29.md). This case derives from the accepted [D01 installed LRU](../D01-installed-lru-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md). It retains the one-aircraft failure and local spare loop, then assigns the system replacement a task breakdown of 10-minute `<REMOVE>` and 20-minute `<REPLACE>`. The [contract](contract.json) and [parent diff](parent-diff.json) freeze the acceptance boundary.

The sealed `e01-v100-ssh-20260929-01` run passed 66 author checks and independent read-only review. The event log shows the explicit split and an item return five minutes earlier than the accepted D01 LRU parent; the aggregate reports remain identical.

Run `python build.py` to verify the frozen input. `python build.py --write` creates the input only if absent.
