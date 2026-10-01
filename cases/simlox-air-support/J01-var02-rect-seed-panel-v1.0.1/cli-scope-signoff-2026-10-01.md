# J01.var02 rectangular preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for twelve fixed-seed,
one-repetition native runs of the B01-derived preparation model. Reusable
publication requires merge to `simlox/main`. This does not complete J01 or
Issue #18.

The accepted `J01.var01@1.0.0` parent input SHA-256 is
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`.
The frozen [panel diff](panel-diff.json) SHA-256 is
`1c8960f8a899fd1011345fccfb30476904aef9b02918569c181f73e38ceb55d9`.
Relative to that parent, seed 01 changes only `MissionPreparation.DURND`
`PREP-DET`→`PREP-RCT` and one `TimeDistributions` row to `PREP-RCT`,
`PFAC=1`, `<RECT>`, lower 0.25 and upper 0.75 hour. The mandatory
`DURN=0.5` hour stays fixed. Seeds 02–12 differ from seed 01 only in
`Control.RSEED`; all retain `NREPS=1`, the same aircraft, notice and mission.
The installed database dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`;
manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
The installed dictionary's `<RECT>` enum resolves the manual p544 `<IRECT>`
spelling inconsistency.

All twelve [indexed](evidence-index.json) runs used guarded session-0 SSH,
the host-wide Issue #18 mutex, and preserved GUI PID 13340/session 1/start
identity. Each import, export, calculation and JSON report completed; every
converter run had zero errors and the known #108/#126 warnings. Each of the
16 source tables with rows roundtripped exactly. Each run records one
preparation beginning at hour 7, a successful mission from hour 8 to 10,
72 System and Stock half-hour bins, and a ready aircraft at the horizon.
Event durations reconcile with integrated report preparation hours.

The twelve logged draws range from 0.30795 to 0.73952 hour, with mean
0.51408 hour and sample standard deviation 0.14484 hour. All are within the
frozen [0.25, 0.75] hour bounds and all twelve differ. The
[author panel replay](review/author-panel-validation-2026-10-01.json) passed
with 132 sealed raw artifacts. The
[independent read-only replay](review/independent-readonly-2026-10-01.json)
passed 19,395 checks with zero failures and independently integrated a
0.514078-hour report mean. Raw artifacts remain under ignored `runs/` paths;
the evidence index publishes run IDs, input/invocation/closure hashes and
every raw artifact SHA-256.

An earlier local 40-repetition diagnostic pair (`J01-var02-rect-preparation-v1.0.0`)
converted and calculated with zero errors but logged only one visible
repetition, so it cannot provide forty per-repetition samples and is excluded
from acceptance. This twelve-seed panel documents observed variation and
sample statistics. It does not prove the population law, sample independence,
endpoint attainment, other RECT parameters or other J01 distribution families,
GUI-only behavior, or cross-engine parity.
