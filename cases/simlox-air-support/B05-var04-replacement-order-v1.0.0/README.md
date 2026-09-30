# B05.var04: rejected replacement subtask order

This negative case derives from the published [E01 local spare replacement](../E01-local-spare-explicit-replacement-v1.0.0/cli-scope-signoff-2026-09-29.md), parent input SHA-256 `84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931`. E01 performs mandatory `<REMOVE>` for ten minutes before `<REPLACE>` for twenty minutes. The child swaps the full type-duration pairs, leaving the task linkage and all other model tables intact; only `ProblemDescription` and `TaskBreakDown` differ. The installed manual's printed pages 400–403 require the removal/replacement order.

The guarded session-0 SSH run `b05-var04-reversed-20260930-01` imported and exported all 20 populated tables exactly, then conversion rejected the invalid sequence with error #163, `Invalid subtask breakdown of sub replacement task: E01-SURP`. It reported one error and warning #108. The calculation process exited zero, but the `.sxo` was only four bytes and no JSON report exists. No mission or repair behavior is accepted from this child.

The [contract](contract.json) and [exact two-table diff](exact-diff.json) were frozen before native execution. The [author replay](review/author-rejection-validation-2026-09-30.json) passed 38 checks. Raw `.sxi`, `.sxo` and logs remain in ignored local `runs/`, sealed by closure SHA-256 `b7b6117c7f7a647a42bfb9af539eaee659fcce246e36ffe41c94c777b44a1a4b`.

The independent [read-only replay](review/independent-readonly-2026-09-30.json) passed 59/59 checks with zero failures and gave GO for this converter-level negative scope only.

Rebuild with `python build.py` and `python describe_diff.py`; replay local sealed files with `python validate_rejection.py` and the independent read-only reviewer. Fresh native execution requires a unique run ID, session-0 SSH, the global Issue #18 mutex and preserved GUI. Omitted, repeated or added subtasks, other replacement pathways, GUI-only behavior and cross-engine parity remain unverified.
