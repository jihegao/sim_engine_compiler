# Independent static review — D11.var04 MNOCC occurrence cap

**Verdict: bounded static GO.** I reviewed the frozen three-branch source, the installed manual and dictionary, the guarded runner, and sealed native logs/reports read-only. This review does not import the author validator. A separate independent full raw replay remains the publication gate.

## Source and contract

- The accepted D10.var02 multi-counter parent input SHA-256 is `0083ffd0038017be0078d9afd5a9e892b3df8c7ae5eafd89b8280950816aa829`. Branch input hashes match the frozen contract: MNOCC=0 `d6bacab5d9ccf99154eb95d7c2b324493bfdc6eca8576d0b76d2cf95a2dee9a3`, MNOCC=1 `548e89ae0e7fede7f604bd7d886a9219b70122530f92fb9a1baa34c6eb3bdd73`, and MNOCC=2 `fb0c75f5bf08ba560cb12a2a9ac7bcb91edf1dc01e983d0e47020cdc92c3c7fc`. Contract SHA-256 is `4557f2e2d762d661f68cc2091b86157e842f6231bcec05ff0e38702b98671610`; exact-diff SHA-256 is `64a579758795f2de889ed11cc6020f68aa97270dd3ce244ac08902e095de25be`.
- I independently compared the 32 source tables. Each child changes only `MaterielPM.MNOCC` from null to its stated 0/1/2 value and descriptive `ProblemDescription`; 30 tables are unchanged. Every pairwise comparison likewise changes only those two tables. The five mission starts 8/16/20/48/52, durations 4/1/1/1/1, PM `MS2` with MISSIONS=2, OPHOURS=3, CALHOURS=24, one-hour subtask, seed 1, and 60-hour result window remain fixed.
- Installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical pp. 374–375, defines MNOCC as the remaining number of times a PM may be performed and specifies zero as never performed; counting starts at simulation start and ignores possible prelife. Installed dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0` defines `MaterielPM.MNOCC` as a nonnegative integer. The contract's 0/1/2 work spans were explicitly pre-run hypotheses.

## Guarded run and raw evidence

- The PowerShell runner parses without errors. It pins each limit to its run ID and source hash, requires session-0 SSH and an `sshd.exe` ancestor, uses `Global\SimloxIssue18NativeQueue`, checks active GUI PID 13340 at preflight and unchanged PID/session/start identity around each hidden CLI step, and writes invocation, step, source, and raw closure evidence. For each of the three runs, all five steps exited 0 with `gui_preserved=true`, source hashes were identical before and after, the invocation SHA matched closure, and I recomputed all 12 raw file byte counts and SHA-256 values with no mismatch. The checker passed 19 row-containing source tables in each. Conversion recorded zero errors and only warnings #108 (simulation log) and #126 (itemless system).
- The sealed run IDs are `d11-mnocc-0-v100-ssh-20261001-01`, `d11-mnocc-1-v100-ssh-20261001-01`, and `d11-mnocc-2-v100-ssh-20261001-01`. Their raw report SHA-256 values, respectively, are `3c0d332a93c13c02381d0b30653116f2132d501621e42d45cfb2de3855be125d`, `548fce45b891ca04191b5e6a9f8c60f773b578018cec543d6e28efcee28ff434`, and `c2b3d7895404894fba72fae0672cc875a0869ddab900bf04d13dffa123d8fd1c`. Closure SHA-256 values are `accb9e6163f91b1630eb370ba21b7d9a9ca7bfc43050e0dad834b52dd0eca9f4`, `fbfe49820c757e8625bacdbc8307ed33e9704cfe17adcb6c1ac07ce1de6863ab`, and `1f9686d5de8236b20f84989aea6794f949009f1e6d821ced0fa84e06099a285a`.

## Observed bounded behavior

| MNOCC | Actual system PM work | Integrated PM occupancy | PM task objects |
| --- | --- | ---: | ---: |
| 0 | none | 0 aircraft-hours | 0 |
| 1 | 12–13 | 1 aircraft-hour | 1 |
| 2 | 12–13 and 21–22 | 2 aircraft-hours | 2 |

All branches have the same five mission starts and successful completions at 12, 17, 21, 49, and 53, with eight operating aircraft-hours. Each report contains 120 half-hour SystemResults and 120 StockTotalResults bins; summary factors MTMF=MSTF=MSUF=STMF equal 1, stock NBO remains zero, and the final [59.5,60) system bin has one ready aircraft with no active PM or failure. Parsed summary and stock rows match across all branches. The differing system fields are PM start/completion markers, PM occupancy, readiness/unavailability, and downtime. In particular, the first `NPMS` marker for the nonzero branches appears in [11,11.5) while the first *actual* PM subtask work starts at 12; the event log, rather than NPMS alone, establishes work timing.

**Limits:** These runs support only the observed cap on actual work for one system-level PM with three counters, one aircraft, one schedule and seed, and no prelife. They do not identify which counter won a given threshold from direct engine telemetry, establish related-PM counter effects, or generalize MNOCC under different missions, resources, PM types, or GUI interaction. The author reports pass 1500 checks per branch, but their assertions were not used as independent evidence here.
