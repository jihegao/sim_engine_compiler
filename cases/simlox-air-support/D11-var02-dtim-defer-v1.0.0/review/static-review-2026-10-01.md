# Independent static and native-evidence review — D11.var02 DTIM=0.3 deferment

**Verdict: bounded GO for the paired observation.** This is a read-only review of sealed run `d11-dtim-defer-v100-ssh-20261001-01` against the frozen diagnostic contract and the DTIM=0 control. A separate independent raw replay remains the acceptance gate.

## Source and provenance

- The direct parent is frozen control input SHA-256 `29e7cdb16e9ab376641edf774a5fc91eb9c44283fd997fa435b79b48423fe901`. Deferred input SHA-256 is `5288d185639174b07c8a062d0ebae7e53cf9bfccbe6936884e58ad15807e9b29`. Exact-diff SHA-256 `6c7179096aef09a8c5ca5222c144189afd189f332f8bd067228f2e2148d56128` records only `MaterielPM.DTIM` 0→0.3 and a descriptive `ProblemDescription` change; 29 other tables, including all six mission waves, are unchanged.
- `PMINT=4`, `OPID=MISSIONS`, and `ATIM=0` remain fixed. Installed manual physical p. 373 rounds an integer MISSIONS deferment upward: `ceil(0.3×4)=2` additional missions. The installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The dictionary permits `MaterielPM.DTIM` in [0,1].
- The runner requires session-0 SSH with an `sshd.exe` ancestor, the host mutex, GUI PID 13340 with stable active session/start identity, and hidden CLI steps. Its closure binds the invocation, pre/post source fingerprints, and 12 raw files. I recomputed all 12 byte counts and SHA-256 values with no mismatch. Five steps exited 0 with GUI identity preserved. The checker passed all 18 source row-containing tables. Conversion recorded zero errors and only warnings #108 (simulation log) and #126 (itemless system).

## Observed result and contrast

- The first four missions match the control: starts at 8, 16, 20, 24; success/return at 12, 17, 21, 25. At hour 25 the log creates PM task 0 and classifies `MS4` **Non-Critical**. It starts the task object, then explicitly pauses it before any positive-duration PM subtask work. The fifth mission preassigns and allocates the aircraft at 25, starts at 25.25, and succeeds at 26.25. At that return `MS4` is still Non-Critical and the sixth mission preassigns. It starts at 26.5 and succeeds at 27.5.
- At the sixth return, the log changes `MS4` to **Critical** and explicitly continues the same paused PM task. Its subtask performs from 27.5 to 28.5. Calling PM “started at 27.5” would obscure the hour-25 task creation; the supported distinction is task object start/pause at 25 versus actual subtask performance at 27.5–28.5. The control instead performs PM at 25–26 and cancels the fifth mission at 25.5833.
- The report has 120 half-hour system and stock rows. Operating exposure integrates to 9 aircraft-hours and PM occupancy to 1 aircraft-hour. `ResultSummary` gives `MTMF=MSTF=MSUF=STMF=1`; stock `NBO` stays zero. The final [59.5,60) system bin is ready with no operation, PM, or failure occupancy. `SystemResults.NPMS` marks [25,25.5), reflecting task creation; occupancy `NSYPM` marks actual work [27.5,28.5).

Raw `model.log` SHA-256: `3b2c54fdae2499522c86654488b5bd341dea47e244f0263179875c4bcd4559b7`; raw report SHA-256: `249dae674b6888446a27846dcd0ee6b45b3293dff9d7d9c88483559db7e04f75`; closure SHA-256: `00a3899d28af34996887c5800cce3999eb4ae21cd50c89f907cab42415425e06`.

**Limit:** The observed task pause/continuation, sixth-return critical classification, and one extra successful mission are supported for this exact queued schedule and seed. They do not establish a generic DTIM scheduling rule or prove behavior for other fractions, anticipation settings, mission tolerances, or multiple aircraft. A separate independent event and per-bin replay should gate publication.
