# J03.var03 bounded CLI acceptance scope

Status: author panel and independent read-only replay GO; PR gates pending.

The accepted parent is `J02.var01@1.0.0` seed 01, SHA-256
`e4dc47f0693d45ed9fbf0f8f4e6e3e68fcf9639f6d843f90201ab5baf675762f`.
The exact source delta is two `COUNTD/<DETERM>` rows at support points 0
and 2, each with PFAC0.5; other business fields are retained, and
seeds 02–32 differ only in Control.RSEED. Contract, panel diff, installed
manual/dictionary and executable hashes were pinned before every run.

Thirty-two fresh accepted one-repetition native runs, separate from 32
excluded probes, passed import/export/calc/JSON report with zero step and
converter errors. Warnings #108, #126, and #211 were classified. Per-run
business roundtrip, source/raw SHA-256 seals, exact mission/aircraft
identities, 72 System/Stock bins, flight hours and terminal six-ready
state passed. The author panel passed with 352 raw seals.

Observed counts are 0 in 15 runs and 2 in 17 runs. The sample mean is
1.0625 and sample variance 1.028225806451613. Positive runs complete
two simultaneous two-aircraft missions at hour 10; zero-count runs
launch none.

Independent read-only replay, without importing the author builder or
validators, passed 45,381/45,381 checks with zero failures across the
32 accepted runs, including all 352 raw seals, 14 populated-table
roundtrips, direct MTMF/STMF values of 0 or 1 by realized count and STACC
integration to four aircraft-hours per mission. Its script and verdict
are in `review/` and bound in `evidence-index.json`.

Publication is limited to these fixed inputs and one installed SIMLOX
version. The 32-seed sample does not prove population 50/50 mixture
weights, stream independence, unobserved behavior, GUI visual content
or cross-engine parity.
