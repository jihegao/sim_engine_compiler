# E15.var01 corrected preflight addendum

**GO for one guarded diagnostic run.** This addendum supersedes the
launch verdict in the original [NO-GO review](static-preflight-2026-10-05.md);
that memo remains as the audit trail. No native process was started during
this recheck, and the fixed run directory is still absent.

The corrected runner SHA-256 is
`32fd6b280271d17210ef38c1f9bd61276e8cc4e3682cccbc8f6bb4792debb7fb`.
PowerShell parsing reports zero AST errors. Contract, input, builder and
checker hashes are unchanged from the original preflight, as is the
one-cell `ItemReorder.ROINT` null→16.0 source contrast.

The warning gate now requires `Form: ItemReorder` followed by `rec 1`
and a warning on that record containing `ROSIZ` and `ignor`. It requires
that warning's code to be the second of exactly two converter warnings,
with #108 first, and Errors 0/Warnings 2/Notes 0. The authored
ItemReorder table has one row, so this binds the ignored-value warning to
the intended item/station record. An unrelated or generic warning can no
longer pass the report gate.

The previously verified 14 source pins, session-0 SSH/`sshd.exe`,
nonblocking global mutex, active protected GUI PID 13340/session 1/start,
hidden target-only watchdog, exact 21-table pre-calculation roundtrip,
unique run path, source before/after seals and immutable raw closure
remain in the runner. The h16 order and report/ledger claims still
require independent post-run verification.
