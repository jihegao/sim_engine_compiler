# B02.var06 no-breakdown control: independent contract review

**Decision: GO_CONTRACT_ONLY.** The frozen contract SHA-256 is `41b8b74938b0b21d7fb2353cc9d5d40d7eb935bcd249084d146483311a7ededa`. It defines a bounded native question and does not approve a runner or native launch. No native run was made for this review.

## Source and provenance

- The catalog lists B02.var06 as the no-breakdown control. At selection, no local or remote owner or published entry for this exact arm was found. The reserved child run ID is `b02-var06-no-breakdown-v010-ssh-20261006-01`.
- Accepted B02 v1.0.2 input SHA `fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34`, contract `9692402d7ab43aa5592ccc7f0020ce6425a183629793c254dc08b764c282ab98`, publication evidence `bceddd5983e9187bf8be19464b04ad5b2136bf665f6d4d9d676928b8c2354c61`, independent review `124fe64f8fe9a70e101ada86da47490d5e5cece87fce717fefc31e1e88f4e0db`, and native closure `3bbaffe3460da2195a4084cb3b92e1fc9c605a5d01380619abf92e3cd107f570` match the inspected files. All 11 parent raw SHA/size seals pass. Its two authored subtasks perform in strict sequence from h7 to h7.5; the mission launches h8 and succeeds/returns h10.
- Accepted B01 v1.0.1 input `2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b` and closure `046a7724f053f63e6967e3c3e803f726fd5f4b6322015239cb25a380c6446516` match; its 11 raw seals pass. B01 has a linked `PREP-FIXED` task without authored `TaskBreakDown` rows. Its log shows a native synthetic `subtask 0 seqno 0`, performing the scalar 0.5 hour from h7 to h7.5. It is a behavioral precedent, not the B02.var06 child result.
- The frozen child input SHA is `7596ea50dc770bf9726a0d3300c0c2b0a881b772e57db0c3a079a3629714a939`. Independent positional comparison with the B02 parent finds only deletion of its two `TaskBreakDown` rows. The empty table remains, along with both unused `SubTaskType` definitions, linked `Tasks`/`MissionPreparation.TID`, scalar `MissionPreparation.DURN=0.75`, `NOPER=1`, seed, 36-hour horizon, and all other source content.

## Manual basis and exact gate

The installed `SIMLOX.pdf` SHA is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Physical page 296 states that the mandatory scalar preparation duration is overridden by the sum of subtasks **when preparation is split**. Pages 402–404 define `TaskBreakDown` as optional, its authored subtasks as sequential, and their summed duration as overriding the main task duration. Keeping the linked task while deleting its two breakdown rows is therefore a coherent way to test fallback to the retained scalar.

The contract correctly requires one synthetic `seqno 0` lifecycle, rather than an absence of all subtask log lines: h7 start, 0.75-hour planned work, h7.75 completion and main preparation completion. It disallows authored SEQ1/SEQ2 lifecycles, wait, cancellation and delay. The same physical aircraft must launch at h8, perform the mission task h8.5–9.5, and succeed/return at h10. These are falsifiable native gates; B01's 0.5-hour precedent does not prove the 0.75-hour child result.

Against the accepted B02 report, the contract permits only two System changes across all 72×40 half-hour cells: in [7.5,8), `NSYMP` 0→0.5 and `NSYMR` 1→0.5. Completion remains within the same bin, so `NPSUC` must match. It requires equality for every other System cell, all 72×16 Stock cells, all 11 summary fields, and `ProblemDescription`. Expected integrals are preparation 0.75, reserved 0.25, flight 2, ready 33 aircraft-hours, with terminal ready 1.

## Prelaunch condition and limits

The prospective roundtrip checker must verify all 16 authored row-containing tables and explicitly confirm the authored `TaskBreakDown` table has no rows. A native export may represent an empty table with an all-null placeholder; any normalization must be confined to that representation, without accepting a populated breakdown row. The later prelaunch review must also verify exact source hashes, zero converter errors with only #108/#126 warnings, substantive SXO/report, unique run directory, SSH session 0/sshd ancestry, free global mutex, protected GUI identity, serial steps, and failure sealing.

The inherited `Tasks.DESCR` still says “Serial 10+20-minute” and is a stale human label. The retained `SubTaskType` rows define available types, not performed work. Any accepted result would cover one fixed seed, one aircraft, one mission, and one linked task without authored breakdown or resources; it would not establish general scalar fallback, other durations/seeds, GUI visual behavior, or full Issue 18 coverage.
