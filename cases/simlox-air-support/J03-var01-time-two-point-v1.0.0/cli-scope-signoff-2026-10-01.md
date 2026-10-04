# J03.var01 bounded CLI acceptance scope

Status: author panel and independent read-only replay GO; PR gates pending.

The accepted parent is `J01.var01@1.0.0`, SHA-256
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`.
The exact model delta replaces one `PREP-DET/<DETERM>/0.5h/PFAC1`
TimeDistributions row with two same-DISTID deterministic rows at
0.25 and 0.75 hour, each PFAC0.5. Seeds 02–32 differ only in
Control.RSEED. Contract, panel diff, installed manual/dictionary and
executable hashes were pinned before every native run.

Thirty-two fresh accepted one-repetition session-0 SSH runs, separate
from 32 excluded probes, passed import/export/calc/JSON report with
zero step and converter errors. Warnings #108 and #126 were classified.
Per-run source/raw SHA-256 seals, 16 populated-table business
roundtrips, exact preparation and mission events, 72 System/Stock
bins, preparation and flight integrals and terminal one-ready state
passed. The author panel passed with 352 raw seals.

Observed preparation durations are 0.25 hour in 15 seeds and 0.75
hour in 17; sample mean 0.515625 hour and sample variance
0.06426411290322581. All preparations began at hour7 and completed
before the hour8 launch. All missions succeeded and completed at
hour10 with two aircraft flight hours.

Independent read-only replay, without importing the author builder
or validators, passed 52,498/52,498 checks with zero failures across
32 accepted runs. It verified all 352 raw seals, 16 populated-table
roundtrips per run, MTMF/STMF=1, STACC integration to two aircraft
flight hours, and terminal readiness. Its script and verdict are in
`review/` and bound by `evidence-index.json`.

Publication is limited to these fixed inputs and one installed
SIMLOX version. The 32-seed sample does not establish population
50/50 mixture weights, stream independence, unobserved behavior,
GUI visual content or cross-engine parity.
