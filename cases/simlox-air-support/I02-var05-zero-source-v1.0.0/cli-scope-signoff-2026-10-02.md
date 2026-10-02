# I02.var05 bounded CLI signoff — zero source stock

**Accepted scope:** A matched h2 one-unit BETWEEN request before an h4 IN,
comparing initial depot stock one versus zero. The accepted I02.var03
parent source SHA-256 is
`4842382bd3728f7f9520d3b20e1ad7148f7436f5132e9cc933773550d64b4560`.
The control changes only `ItemTransfer.TFTIME` 6→2 and description; its
source SHA-256 is
`c7b4b0214bb9d5182711984d460eeff61cb31e06a0e62d019704f2723ca13c3e`.
The child changes only depot `StockAllocation.STSIZ` 1→0 and description;
its source SHA-256 is
`00cebb18be952522b1bbfd1885edc40f2c9b4da148d000cf5326309360cc6453`.
The two-step exact-diff SHA-256 is
`dec6de4351142dadee2cce8d2c87278242512f4319c45db6e55b30ef9490bdd0`.
Each contrast leaves 30 other tables unchanged.

The two serial session-0 SSH native runs preserve GUI PID 13340, each
complete five steps, convert with zero errors and one expected logging
warning, and round-trip 22 populated authored tables. At h2, control
physical ID 0 leaves depot and arrives at base. Child h2 task starts and
arrives with zero items while adding transfer backorder one; no physical
item moves. At h4, child IN adds physical ID 0 at depot, clears the transfer
backorder, and a second BETWEEN task delivers that ID to base.

Four report-only exports from the sealed SXOs expose 72 half-hour native
`ItemResults` bins per arm/station. Both base nominal `STSZ` series rise
to one at h2. Control base on-hand `STOHA` rises at h2; child base on-hand
stays zero until h4. Child depot nominal/on-hand remain zero. Later, child
ordinary depot backorder `NBO=1` begins h10, declines within the h13–13.5
bin as failed ID 1 is repaired at h13.1667, and is zero afterward. Base
receives ID 1 at h15.1667 and terminal on-hand is one. Control depot/base
terminal on-hand is one each; child depot/base terminal on-hand is zero/one.
Selected `SystemResults`, `StockTotalResults`, `ResultSummary`, and mission
tables match; both station `ItemResults` and `ItemResultsTotal` differ.

Author read-only replay passed 34/34 checks. Independent read-only replay
passed 1717/1717 checks and returned bounded GO. Six closures seal 12 native
raw files per arm and two report files for each of four station exports,
32 total. `evidence-index.json` pins the source, local run paths and
raw SHA-256 hashes. Proprietary selectors and native raw files stay local
and ignored by Git.

**Boundary:** This establishes one zero-source scheduled BETWEEN before a
later IN against a matched available-source control, one unit, one seed and
two stations. Child target `STSZ=1` at h2 with `STOHA=0` and an open
transfer backorder is a native nominal-position observation; it is not a
physical arrival. Arbitrary quantities, standalone transfer without later
IN, general priority, reorder/procurement, positive delay, GUI visual
behavior and cross-engine parity remain unverified. I02 and Issue #18 stay
open.
