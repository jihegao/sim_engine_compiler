# D11.var03 short-delay ENREG=Y: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for original-calendar-grid retention in one fixed short delay, paired with `ENREG=N`. Publication requires merge to `simlox/main`. This does not complete D11 or Issue #18.

Frozen control input SHA-256 `61643f14212e7195437da7d95da91458472b29ac65555287cf968c66aee61bb1`; installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` (physical pp. 204, 370, 372–374); dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The manual describes `ENREG=Y` as retention of the original schedule after delay.

Frozen [contract](contract.json) SHA-256 `2428d3a4249c16e14a33dd3eeb7288122faa8cdc6050f0e90efc59e96b6b2bee`; [input](native-input.json) SHA-256 `3e64d0d817e1185cc95f826f0c5940bbfcf1bb9ee3f7af79d2046b91e11a2370`; [exact control diff](exact-diff.json) SHA-256 `d89085b2810b257eef63347ff3fec6083844e6a774536f521d30c8a8298e9a5d`. Only `MaterielPM.ENREG` changes N→Y plus description; 29 tables remain equal.

Guarded session-0 SSH run `d11-enreg-regular-v100-ssh-20261001-01` completed five native steps and exact 18-table roundtrip under `Global\SimloxIssue18NativeQueue`, preserving GUI PID 13340/session 1/start identity. Conversion errors were zero; #108 logging and #126 item-free warnings were expected. The closure seals 12 raw artifacts with unchanged source hashes; its SHA-256 is `302566829caa88f79acbf1ef1387486a068161cc04704812a9439e277695b1fd`.

All three missions succeed at 10, 22 and 25.5. The `NPMS` marker at 24 records the due threshold during flight; first actual PM work is 25.5–26.5. The second PM works at 48–49 on the original 24-hour grid, versus 50.5–51.5 with `ENREG=N`. All 120 half-hour System and Stock-total bins reconcile six flight and two PM aircraft-hours, no failure or stock demand, summary factors 1 and terminal ready. [Author replay](review/author-validation-2026-10-01.json) passes 1,501/1,501 checks; [independent read-only replay](review/independent-readonly-2026-10-01.json) separately checks raw evidence. The [evidence index](evidence-index.json) hashes local ignored `runs/` artifacts.

This pair establishes one short-delay contrast. The [long-delay ENREG=Y case](../D11-var03-enreg-long-regular-v1.0.0/cli-scope-signoff-2026-10-01.md) separately checks omission. Other intervals, mission delays, PM competition, GUI-only behavior and cross-engine equivalence remain unverified.
