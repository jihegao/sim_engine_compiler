# I02.var05 bounded CLI signoff — source shortage

**Accepted scope:** Against accepted I02.var03, change only the h6
`DEPOT-01`→`BASE-01` `ItemTransfer.TFQTY` from one to three and the
description. The parent source SHA-256 is
`4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560`;
child SHA-256 is
`1f31540862de0f586eeacea5907be7f9fa238ae54ba4657f7211c1b64f58f1a3`;
exact-diff SHA-256 is
`6e1e76f5237fa617c3734f556a35aa5d85248047ec3e87b5971bb6dd44fc5586`.
Thirty other tables remain unchanged. The h4 IN raises depot stock from one
to two before the h6 request.

The guarded session-0 SSH native run
`i02-var05-qty3-v100-ssh-20261002-01` preserved GUI PID 13340,
completed all five steps, converted with zero errors and one expected
simulation-log warning, and round-tripped 22 populated authored tables.
At h6 it moves physical IDs 0 and 1 to base and adds a one-unit transfer
backorder. At h10 a separate ordinary depot backorder is added as aircraft
demand uses base ID 0. Repaired mounted ID 2 reaches depot at h13.1667;
the transfer backorder is removed and a second BETWEEN task moves ID 2 to
base. The ordinary backorder remains. This is a direct observed instance of
the transfer request receiving that item first, not a general scheduling
priority proof.

Two sealed-SXO report-only exports expose native `ItemResults` with 72
half-hour bins per station. At h6, depot `STSZ`/`STOHA` fall 2→0 while
base `STSZ` rises 0→3 and `STOHA` rises 0→2. The full target nominal
increase occurs at the first partial physical transfer; one transfer
backorder still exists. The source `NBO` ordinary backorder rises 0→1
at h10 and remains one to h36, whereas the h6 transfer backorder is tracked
separately in the physical log. Unchanged aggregate `StockTotalResults.NBO=0`
does not negate the depot item-position backorder. Terminal depot `STSZ`/`STOHA` are zero;
base `STSZ` is three and `STOHA` two. System, aggregate stock and mission
tables match the one-unit parent. Both station `ItemResults` and
`ItemResultsTotal` differ, as expected from the transfer quantity.

Author read-only replay passed 29/29 checks. Independent read-only replay
passed 1222/1222 checks and returned bounded GO. Three closures seal 12 native
raw files and two files for each station report, 16 total. The evidence index
pins source files, run IDs, raw SHA-256 hashes, and proprietary selector
hashes; raw and selector files remain local and ignored by Git.

**Boundary:** This is one available-two/request-three BETWEEN after IN,
zero TFDT, one seed, one LRU type and two stations. The target nominal
`STSZ=3` at h6 is an observed native value, despite a one-unit transfer
backorder; the installed manual's general per-performance wording is not
promoted to an exact nominal timing rule here. Zero-stock, arbitrary splits,
general priority, lateral support, reorder/procurement, delayed transfers,
GUI visual behavior and cross-engine parity remain unverified. I02 and
Issue #18 remain open.
