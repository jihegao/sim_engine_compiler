# J01.var03 triangular preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for twelve fixed-seed,
one-repetition native runs of the B01-derived preparation model. Reusable
publication requires merge to `simlox/main`. This does not complete J01 or
Issue #18.

The accepted `J01.var01@1.0.0` parent input SHA-256 is
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`.
The frozen [panel diff](panel-diff.json) SHA-256 is
`7c29672b22502400ed629cf15b134620487566fb95f3244a1d1897c136402efa`.
Relative to that parent, seed 01 changes only `MissionPreparation.DURND`
`PREP-DET`→`PREP-TRI` and one `TimeDistributions` row to `PREP-TRI`,
`PFAC=1`, `<TRIANG>`, lower 0.25, mode 0.5 and upper 0.75 hour. Mandatory
`DURN=0.5` hour stays fixed. Seeds 02–12 differ from seed 01 only in
`Control.RSEED`; all retain `NREPS=1`, one aircraft and one scheduled mission.

The installed database dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`;
manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
Manual pp. 543–545 give lower/mode/upper parameter order but spell the
triangular base `<TRIANGULAR>`; the installed dictionary lists `<TRIANG>`.
All twelve native import/export cycles accepted and retained `<TRIANG>`.
This evidence resolves that literal token for the tested installed version.

All twelve [indexed](evidence-index.json) runs used guarded session-0 SSH,
the host-wide Issue #18 mutex, and preserved GUI PID 13340/session 1/start
identity. Each import, export, calculation and JSON report completed; every
converter run had zero errors and the known #108/#126 warnings. Each of the
16 source tables with rows roundtripped exactly. Each run records one
preparation beginning at hour 7, a successful mission from hour 8 to 10,
72 System and Stock half-hour bins, and a ready aircraft at the horizon.
Event durations reconcile with integrated report preparation hours.

The twelve logged draws range from 0.35812 to 0.67606 hour, with mean
0.51392 hour, sample standard deviation 0.10766 hour and twelve distinct
values. All lie within the frozen [0.25, 0.75] hour support. The
[author panel replay](review/author-panel-validation-2026-10-01.json) passed
with 132 sealed raw artifacts. The
[independent read-only replay](review/independent-readonly-2026-10-01.json)
passed 19,432 checks with zero failures; its report-integrated range is
0.358116–0.676061 hour and mean 0.513918 hour. The independent script
SHA-256 is `a4e57500dacf3e3229cbee7fbca64ed63b599e504d614f9422249acdad2a27f6`;
its verdict SHA-256 is
`6677da2262475a9cd0ba6a4422e42d402f658edd0c56dcc08bed8aa770efaf1b`.
Raw artifacts remain under ignored `runs/` paths; the evidence index
publishes run IDs, input/invocation/closure hashes and each raw SHA-256.

The panel documents native acceptance and observed varied preparation
durations for these twelve seeds. It does not prove the population law,
mode, sample independence, endpoint attainment, other TRIANG parameters
or distribution families, GUI-only behavior, or cross-engine parity.
