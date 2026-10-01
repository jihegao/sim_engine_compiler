# D11.var03 long-delay ENREG=Y: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for one long calendar-PM delay with an intervening planned slot omitted, paired with `ENREG=N`. Publication requires merge to `simlox/main`. This does not complete D11 or Issue #18.

Frozen long-drift control input SHA-256 `76836c8b1dd8f9d5552e9fb908b766e80995bc9fdcd7b7967f75a73de6f6b7c5`; installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` (physical pp. 204, 370, 372–374); dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The manual limits omission of PMs scheduled during delay to calendar PM with `ENREG=Y`.

Frozen [contract](contract.json) SHA-256 `a880ef83511ff3e4035b7f292720936a63d800df293c4d6c97cd127139517e91`; [input](native-input.json) SHA-256 `a7f41c9e202c136760ea22c67aecf5abe52a55331c60590694ca012521a34f30`; [exact control diff](exact-diff.json) SHA-256 `35c84c31c5570b9680a8dea75cfd6edcbc8431176d4f847c60a0238a489e50f6`. Only `MaterielPM.ENREG` changes N→Y plus description; 29 tables remain equal.

Guarded session-0 SSH run `d11-enreg-long-regular-v100-ssh-20261001-01` completed five native steps and exact 18-table roundtrip under `Global\SimloxIssue18NativeQueue`, preserving GUI PID 13340/session 1/start identity. Conversion errors were zero; #108 logging and #126 item-free warnings were expected. The closure seals 12 raw artifacts with unchanged source hashes; its SHA-256 is `e2b6d51541f1b96b4da918a1cfbf1057aa0c45a81135801dc942f93b610d53b7`.

All three missions succeed, with the long flight at 23.5–49.5 crossing planned PM slots 24 and 48. The first `NPMS` marker at 24 denotes the due threshold during flight; PM task/subtask work occurs once on return at 49.5–50.5. No immediate catch-up PM is created for the hour-48 slot. The next PM works 72–73 on the original grid, versus 74.5–75.5 with `ENREG=N`. All 168 half-hour System and Stock-total bins reconcile 30 flight and two PM aircraft-hours, no failure or stock demand, summary factors 1 and terminal ready. [Author replay](review/author-validation-2026-10-01.json) passes 2,077/2,077 checks; [independent read-only replay](review/independent-readonly-2026-10-01.json) separately checks raw evidence. The [evidence index](evidence-index.json) hashes local ignored `runs/` artifacts.

This is one fixed calendar-PM omission observation. Other delay lengths, intervals, interacting PMs, noncalendar OPIDs, GUI-only behavior and cross-engine equivalence remain unverified.
