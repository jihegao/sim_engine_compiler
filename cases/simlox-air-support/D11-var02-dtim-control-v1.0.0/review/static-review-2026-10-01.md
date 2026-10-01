# Independent static and native-evidence review — D11.var02 DTIM=0 control

**Verdict: bounded GO for this control observation.** This is a read-only review of the sealed run `d11-dtim-control-v100-ssh-20261001-01`; a separate independent raw replay remains the acceptance gate. The frozen contract treated PM timing and queued-mission outcomes as hypotheses.

## Source and provenance

- Accepted direct parent D11.var01 ATIM=0 input SHA-256: `94c0addbaff610b656b25dd328949ea9710ab9a593cafebe488f7bfca665ead8`. Frozen child input: `29e7cdb16e9ab376641edf774a5fc91eb9c44283fd997fa435b79b48423fe901`. The exact-diff artifact SHA-256 is `ac72fe5727be6827601e7292277bb38151712fbd84c8187606ef1fc45286ec4b`: only `OperationProfile` and descriptive `ProblemDescription` change; 29 tables are unchanged.
- Six scheduled waves start at 8, 16, 20, 24, 25.25, and 26.5 hours. Mission durations are 4, 1, 1, 1, 1, and 1 hour. `MaterielPM` remains `MISSIONS`, `PMINT=4`, `ATIM=0`, `DTIM=0`; `Control.ENPM=Y`, seed 1, and the 60-hour simulation and result windows remain fixed. The installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. Manual physical pp. 204 and 370–374 and dictionary `MaterielPM` columns support this MISSIONS/DTIM model.
- The runner requires session-0 SSH with an `sshd.exe` ancestor, acquires `Global\SimloxIssue18NativeQueue`, checks GUI PID 13340 and its active session/start identity, invokes the CLI in hidden windows, and records pre/post source hashes. The closure binds the invocation and 12 raw files; I recomputed all 12 file byte counts and SHA-256 values with no mismatch. All five steps exited 0 with GUI identity preserved. The 18 source row-containing tables passed the roundtrip checker. Conversion recorded zero errors and only warnings #108 (simulation log) and #126 (itemless system).

## Observed result

- The first four mission IDs start at 8, 16, 20, and 24 and succeed at 12, 17, 21, and 25. At hour 25 the log classifies `MS4` **Critical** and starts the PM subtask, which performs from 25 to 26.
- The fifth requested mission waits from 24.25 and cancels at 25.5833. The sixth request waits from 25.5, allocates the same aircraft after PM completion at 26, starts at 26.5, and succeeds at 27.5. Thus five of six requested missions succeed; the control is not a blanket denial of all post-threshold missions.
- The report has 120 half-hour `SystemResults` and 120 `StockTotalResults` rows. System operating exposure integrates to 8 aircraft-hours and PM occupancy to 1 aircraft-hour. `ResultSummary` has `MSTF=MSUF≈0.8333333` and `MTMF=STMF≈0.8888889`; stock `NBO` remains zero. The final system bin [59.5,60) is ready, with no operation, PM, or failure occupancy.

Raw `model.log` SHA-256: `0e094aaf901d15c2b8b66895e77cb7ac147e4fabe6f984205ed8bb2702117637`; raw report SHA-256: `f9d99321e2788a031866406e31cdec40d07075b59ad243bb58bf20863770e16d`; closure SHA-256: `4e35f88432caedbec777915f76b0b82e118534b505f7bb58dc7c0ff685936846`.

**Limit:** This is one fixed queue schedule and one seed. Mission preassignment and same-time return ordering affect the outcome. Do not generalize DTIM=0 to other schedules or infer a universal PM-versus-mission priority rule from this run. A separate independent event and per-bin replay should gate publication.
