# J03.var02 mixed preparation-time distribution

This bounded case derives from accepted `J01.var02@1.0.1` seed 01.
The `TimeDistributions` `PREP-RCT` row changes from one
`<RECT>/0.25..0.75/PFAC=1` row to two same-DISTID rows:
`<DETERM>/PARAM1=0.25/PFAC=0.5` and
`<RECT>/PARAM1=0.5/PARAM2=0.75/PFAC=0.5`. The mandatory
`MissionPreparation.DURN=0.5` hour and `DURND=PREP-RCT` stay.
One aircraft, hour-8 scheduled launch, one-hour notice, two-hour
mission and hour-36 horizon remain. Seeds 02–32 change only
`Control.RSEED`. `build.py --check` verifies the accepted parent
fingerprint and exact source diff.

Thirty-two excluded diagnostic runs fixed the observation sequence.
Thirty-two fresh accepted session-0 SSH runs reproduced 15 preparation
durations of 0.285714 hour and 17 distinct durations from 0.603545 to
0.84389 hour. The sample mean is 0.5157150625 hour and sample
variance is 0.051992252105995965. Each preparation begins at hour7;
all finish before the hour8 mission start. Every mission succeeds at
hour10. Reports have 72 aligned System/Stock bins, preparation
integrals matching the event log, two aircraft flight hours, no stock
demand and the aircraft ready at horizon.

The observed values differ from the nominal component supports. The
configured component mean is 0.4375 hour while
`MissionPreparation.DURN` is 0.5 hour. Their ratio is 8/7: the
0.285714-hour spike matches `0.25 × 8/7`, and all 17 other draws
lie within the corresponding scaled interval
`[0.5 × 8/7, 0.75 × 8/7]`. This is a model-specific inference
corroborated by all 32 native outputs. The installed manual on page
511 says the scalar and distribution interact when both are given,
but does not specify this exact normalization formula. The manual
defines PFAC and component parameters on pages 541–545.

The runner uses authenticated session-0 SSH, the host-wide Issue #18
mutex, exact source and installed manual/dictionary/executable hashes,
and a start-identity guard for GUI PID 13340. Every accepted run
records four native steps and seals 11 raw files. The ignored local
`runs/` directory holds the raw evidence. `validate.py RUN_DIRECTORY
SEED` replays one run without SIMLOX; `validate_panel.py` replays the
32 accepted runs and descriptive statistics. `evidence-index.json`
records run IDs and SHA-256 seals. On a clean checkout without
existing runs, use the matching seed hash from `panel-diff.json`;
the runner requires `j03-var02-seedNN-accepted-20261001-01`.

These fixed outputs do not establish component selection probabilities,
the conditional rectangular population law, the general normalization
algorithm, stream independence, unobserved values, GUI visual content,
or cross-engine parity.
