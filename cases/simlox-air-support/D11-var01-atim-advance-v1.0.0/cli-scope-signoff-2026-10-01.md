# D11.var01 ATIM advance: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for `MISSIONS=4`, `ATIM=0.3` against the frozen zero-ATIM control. Publication requires merge to `simlox/main`. This pair does not complete D11 or Issue #18.

The accepted control input SHA-256 is `94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8`. Installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` (physical pp. 202, 204, 370, 372–374); dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The manual gives an integer mission-count front shift: `floor(0.3 × 4)=1`.

Frozen [contract](contract.json) SHA-256 is `4d398939ed7a50ee00cc4eabbcd862e8b107cde8f34e597f871364cd06d5472f`; [input](native-input.json) SHA-256 is `d408ce1f556619cafd81a837b6cfead2a92de8083c651f7b0487575eef684fa3`. The [exact control diff](exact-diff.json) SHA-256 is `c64bf2d49e9122171cacccd170c7e70ffde4c9415da9e6934ea8cf574d27320b`: only `MaterielPM.ATIM` changes from 0 to 0.3 plus a descriptive label. Mission waves and one-hour PM task are otherwise equivalent.

Guarded session-0 SSH run `d11-atim-advance-v100-ssh-20261001-01` completed import, export, calculation, JSON report and exact 18-table roundtrip under `Global\SimloxIssue18NativeQueue`, preserving GUI PID 13340/session 1/start identity. Converter errors were zero; #108 logging and #126 item-free warnings were expected. The closure seals 12 raw artifacts with unchanged source hashes; its SHA-256 is `90d0220a4a730fa714f85645ab349bd11f6a44806464fa0411e0d0cc1c2a7877`.

Five missions succeed at hours 12, 17, 21, 49 and 53. The log identifies one `MS4` PM task and one-hour subtask at 21–22, after the third return, versus 49–50 in the control. No second PM occurs through hour 60. The report has 120 half-hour System and Stock-total bins, eight flight aircraft-hours, one PM aircraft-hour, no failures or stock demand, and a ready aircraft at hour 60. [Author read-only replay](review/author-validation-2026-10-01.json) passes 1,500/1,500 checks. [Independent raw replay](review/independent-readonly-2026-10-01.json) is separate. Raw SXI/SXO, log and report remain local under ignored `runs/`; [evidence index](evidence-index.json) supplies their IDs, lengths and SHA-256 hashes.

This fixed pair establishes the one-mission ATIM advance for this schedule. Other fractions, `DTIM`, `ENREG`, `MNOCC`, competing PM, resources, GUI-only behavior and cross-engine equivalence remain unverified.
