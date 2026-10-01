# G05.var06 nested passive switch: bounded CLI sign-off

**Decision:** accept and publish the fixed-seed CLI behavior of a two-branch passive B/A child nested under a nonfailing POS-C series leg. GUI RBD rendering and cross-engine equivalence were not observed.

## Source and mechanism

- Accepted direct parent: `G05-passive-switchover-v1.0.0/half-input.json`, SHA-256 `d5a38dcb0006f3a2dc6447bdafdeb5c5e5a98b8eb2ccb49db57fa2801ae76c20`, native run `g05-passive-half-v100-ssh-20261002-01`.
- Schema reference: accepted G04 nested AND input, SHA-256 `658cdfcc374a13754c0980888137dd05bb0b94c4dfad5386bab5292fc414dd15`; only its `RBDSeries` table schemas are copied. Native child input SHA-256 `acefc1855fe55cdb9f977c5545ad3d5f780dfc78687c17aa9ce74acbb765dd62`; exact-diff SHA-256 `158405e639acfcbf2a51625ce3fbc8992be65ba46c5ba893553217e826b2f070`.
- Four existing tables change (`ProblemDescription`, `MaterielOperationalModes`, `RBDParallel`, `RBDParallelStructure`) and two series tables are added. POS-C leaves the standby list and becomes a required series leaf. The passive B/A child keeps `NBREQ=NBOP=1`, B priority 1, A priority 2, `TSWOV=0.5 h`, `ONLM=N`. Its nested `OPMID` is null per installed manual p770. All mission, failure, CM, stock, seed and report rows remain the accepted parent's values.
- Installed source SHA-256: SIMLOX executable `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; manual `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; dictionary `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`.

## Native run and behavior

- Run ID `g05-nested-v100-ssh-20261002-01`. Session-0 SSH with an `sshd.exe` ancestor and host mutex `Global\SimloxIssue18NativeQueue`; existing GUI PID 13340/session 1/start identity preserved. Five guarded steps (import, export, calc, JSON report, roundtrip check) exit zero. Exactly 25 populated authored tables roundtrip unchanged, conversion errors zero, SXI/SXO/log/report nonempty. The raw invocation, closure and 12 child raw files are sealed in `evidence-index.json`.
- The mission starts h8. Operated POS-B fails h8.94145 and a noncritical B→A switch ends h9.44145. POS-A fails h17.5636; without POS-C as a standby rescue branch, the second fault is critical and the mission aborts at that instant. Aborted return is h24.0636. B/A direct CM tasks run concurrently h24.0636–24.5636, and the system is ready at the h36 horizon. No POS-C failure occurs.
- All 72 half-hour `SystemResults` and `StockTotalResults` rows align. System-level `NSYSW` integrates to 0.5 h in bins 8.5–9 and 9–9.5, matching the sole child switch. The report has two failures, two repairs, 0.5 h in repair, terminal ready 1, and zero stock demand/backorders/movement. `ResultSummary.MSUF=0`. The accepted parent has the same B/A failure instants but adds A→C switching, integrates one hour of switch state, and succeeds (`MSUF=1`).
- Author raw replay: 24/24 checks, SHA-256 `48d57b9fbb5cf3e98639bc49dcfe01bbb1daebdc7b2f32df8d8108b04070e955`. Independent read-only replay: 1,742/1,742 checks, GO; checker SHA-256 `0ed4bb9469664ae4b48a51fcd3788593f58243bee578a7d4f1346ba593857efe`, verdict SHA-256 `01e9eea7258b1585c2be9782086028246591cf6ee98ebfd9e0edac53c925f85a`.

## Scope limits

The event log names the passive child's B→A switch and aircraft fault state, not a separate series-root transition. The root interpretation relies on the frozen topology, system-level switch occupancy and critical abort, corroborated by the accepted parent contrast. Moving C also removes the rescue route; this case proves this **specific nested configuration's** observed propagation and outcome, not an isolated universal nesting rule or a full truth table. It uses one seed, one repetition and one 0.5-hour switch. `G05.var04` unavailable preferred standby, `G05.var05` overlapping switches, other seeds, GUI RBD rendering and cross-engine parity remain unverified. The separately drafted unavailable-standby design failed independent pre-run review and was not run or published.
