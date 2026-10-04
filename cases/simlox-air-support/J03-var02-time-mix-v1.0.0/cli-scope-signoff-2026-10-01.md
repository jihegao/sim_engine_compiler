# J03.var02 bounded CLI acceptance scope

Status: author panel and independent read-only replay GO; PR gates pending.

The accepted parent is `J01.var02@1.0.1` seed 01, SHA-256
`ee867ced23e4fa2d988e22fa13742055b5cdbbc64df875030feab5bf7060c724`.
The exact model delta changes one `PREP-RCT` TimeDistributions
`<RECT>/0.25..0.75/PFAC1` row to `<DETERM>/0.25/PFAC0.5` and
`<RECT>/0.5..0.75/PFAC0.5`, retaining
`MissionPreparation.DURN=0.5` and `DURND=PREP-RCT`. Seeds 02–32
change only Control.RSEED. Contract, panel diff, installed
manual/dictionary and executable hashes were pinned before each run.

Thirty-two fresh accepted one-repetition session-0 SSH runs, separate
from 32 excluded probes, passed import/export/calc/JSON report with
zero step and converter errors. Warnings #108 and #126 were classified.
Per-run source/raw SHA-256 seals, 16 populated-table business
roundtrips, exact preparation and mission events, 72 System/Stock
bins including fractional NSYMP, preparation/flight integrals and
terminal one-ready state passed. The author panel passed with 352
raw seals.

The native event log records 15 durations of 0.285714 hour and 17
distinct durations from 0.603545 to 0.84389 hour. Sample mean is
0.5157150625 hour and sample variance is 0.051992252105995965.
All preparation starts at hour7 and ends before hour8; all missions
launch hour8 and succeed hour10. The configured mixture's nominal
mean is 0.4375 hour, while `MissionPreparation.DURN` is 0.5 hour.
The 8/7 ratio fits the observed spike and interval; this is a
model-specific inference, not an explicit manual formula or general
engine law.

Independent read-only replay, without importing the author builder or
validators, passed 52,501/52,501 checks with zero failures across
32 accepted runs, including all 352 raw seals, 16 populated-table
roundtrips per run, MTMF/STMF=1, STACC integration to two aircraft
flight hours and terminal readiness. Its script and verdict are in
`review/` and bound by `evidence-index.json`.

Publication is limited to these fixed inputs and one installed SIMLOX
version. It does not establish component probabilities, a conditional
rectangular population law, an exact general scaling algorithm,
stream independence, unobserved behavior, GUI visual content or
cross-engine parity.
