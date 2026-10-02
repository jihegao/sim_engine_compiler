# G11.var05 v1.0.0 CLI scope sign-off — 2026-10-03

**Decision: bounded GO.** One blank final `PrelifeData.QTY` row receives exactly two of four deployed top-level systems, reproducing explicit `QTY=2` ages and first PM timing. This does not certify reordered rows or invalid-QTY behavior.

## Source and frozen model

The accepted G11.var01 `fixed-ages` input SHA-256 is `a8836588aa09973b78195cf515cdc1ed4916c4f1653690e3bbd38fd0a5fb4bd2` and its native closure SHA-256 is `29238ff0dfe1f92eca8876033987e2c6cdbd119335e51a625d82685076c45796`. Installed 2017 manual and dictionary hashes are `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` and `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. Manual physical pages 468–471 permit one blank QTY to take remaining materiel and prohibit explicit totals above deployment quantity; page 209 describes blank-QTY PLIND placement last. The [contract](contract.json) SHA-256 is `a4f9d043c0eef8d568d3c56ec6e02bd1f2738949f206b25b228338d491d31bb2`; [exact diff](exact-diff.json) SHA-256 is `d717f8375b8b5eb56a3f82c8a1087c01ca4bbb4cdc8e0132a0a5480a468012b7`.

Both arms raise `SystemDeployment.QTYPS` from 3 to 4 and set the three referenced OperationProfile `IQTY` cells to 0. All other parent settings, including CAL100, seed1 and 104-hour horizon, remain. The pair changes only the AGE120 row's `PrelifeData.QTY` from 2 to blank and description; AGE0/QTY1 and AGE60/QTY1 stay fixed. Input SHA-256s are `afd693a6609c2454b3ec71a1f663791b61a932831720070d164d371c6aff9be2` and `056728b5db95e06d5152337c4ec4b706cc8c69981bb094fd4f8f85102875be71`.

## Native and independent evidence

Run IDs `g11-var05-explicit-two-v100-ssh-20261003-01` and `g11-var05-remaining-blank-v100-ssh-20261003-01` have closure SHA-256s `c7bbb656aec910fba20388022f11531db50c2bdefc1cf3d41c820db4106dac3a` and `8318e7e28e8b6238b2662e16d35fac2a2710b11dd8fecfa34c375d4d3582f9`. Both used authenticated session-0 SSH, host-wide `Global\SimloxIssue18NativeQueue`, hidden native CLI processes, GUI PID13340/session1 guards at every step, source before/after seals, and temporary Prelife Log option restoration to `NO`. Import/export, calculation, report export, and the roundtrip check completed with exit0. Each arm roundtripped all 20 populated authored tables, converted with zero errors/notes and only known #108 event-log and #126 itemless-system warnings, and sealed 13 local raw files. The [evidence index](evidence-index.json) SHA-256 is `8034dea0df8bf84dd1179a15c2d9893ddab2225a507ba20af7969bbf7fe12273`; 12/12 published source and 26/26 raw records verify.

The Prelife Logs are byte-identical, listing `AGE0` age0, `AGE60` age60, and two `AGE120` age120 systems. The native event logs are byte-identical, with first CAL100 PM starts ID1 h40, IDs2 and3 separately at h80, and ID0 h100; all complete exactly one hour later. No missions, resource bookings, stock demand, failures, or backorders occur. Each report has 208 contiguous half-hour System and 208 Stock bins, `NPMT=NPMS=4`, `NFAIL=0`, and terminal ready=4. The two concurrent hour-80 PMs are distinct entity events, not one doubled task. The default report has no selected per-item or ResourceResults table; the no-resource requests are visible in the native event log.

The [author replay](author-validation.json) passes 188/188 checks. The separately written [independent replay](independent_replay.py) imports no author implementation and its [verdict](independent-verdict.json) passes 21,427/21,427 checks; independent script SHA-256 `54563e662c64de83e36353acfd94626c21c20e62e13d283bbc7fe5612bbb5820`, verdict SHA-256 `822b09ee2fc3b000ec734d937910b1a47b3eb7e39013cef963e734304b841bf9`.

## Limits

The blank row is last and is the only blank within one PLID. This validates remaining allocation, not row-order effects, multiple blank rows, over-allocation, or missing intermediate structures. It covers four same-type top-level systems, fixed CALHOURS ages, one seed and first PM only. Installed/stocked item prelife, later PM cycles, other OPIDs, GUI visual behavior and cross-engine equivalence remain unverified.
