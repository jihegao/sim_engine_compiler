# J01.var04 exponential preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for twelve fixed-seed,
one-repetition native runs of the B01-derived preparation model. Reusable
publication requires merge to `simlox/main`. This does not complete J01 or
Issue #18.

The accepted `J01.var01@1.0.0` parent input SHA-256 is
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`.
The frozen [panel diff](panel-diff.json) SHA-256 is
`ecf569cbf61d8ae16a10395be88fd4f7fda718b911f56e111f5f8816d2b515d1`.
Relative to that parent, seed 01 changes only `MissionPreparation.DURND`
`PREP-DET`→`PREP-EXP` and one `TimeDistributions` row to `PREP-EXP`,
`PFAC=1`, `<EXP>`, mean `PARAM1=0.5` hour and empty `PARAM2`/`PARAM3`.
Mandatory `DURN=0.5` hour stays fixed. Seeds 02–12 differ from seed 01
only in `Control.RSEED`; all retain `NREPS=1`, one aircraft and one mission.

The installed database dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`;
manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
Manual p. 511 allows `<EXP>` directly for mission preparation, while its
general parameter table on pp. 543–545 spells the exponential base
`<NEGEXP>` and gives `PARAM1` as the mean. The installed dictionary lists
`<EXP>`; all twelve native import/export cycles accepted and retained it.

All twelve [indexed](evidence-index.json) runs used guarded session-0 SSH,
the host-wide Issue #18 mutex, and preserved GUI PID 13340/session 1/start
identity. Each import, export, calculation and JSON report completed;
converter errors were zero with the known #108/#126 warnings. Each of the
16 source tables with rows roundtripped exactly. Every run has one positive
preparation starting at hour 7, one successful mission, 72 System and Stock
half-hour bins, two integrated flight hours, and a ready aircraft at the
horizon. Event preparation durations reconcile with report preparation
hours. Seed 09 alone takes 1.07748 hours of preparation and overruns the
one-hour notice: its mission starts at hour 8.07748 and succeeds near
10.0775. The other eleven launch at hour 8 and succeed at hour 10.

The twelve logged draws range from 0.01059 to 1.07748 hour, with mean
0.41626 hour, sample standard deviation 0.35867 hour and twelve distinct
values. The [author panel replay](review/author-panel-validation-2026-10-01.json)
passed with 132 sealed raw artifacts. The
[independent read-only replay](review/independent-readonly-2026-10-01.json)
passed 19,459 checks with zero failures; its report-integrated range is
0.010592–1.077481 hour and mean 0.416264 hour. Independent script SHA-256
is `84ed492293cca337950ccf27a4e5ccaf1118b307619215b1680457a8460d5198`;
verdict SHA-256 is
`dce98c1cb56d14af1f8707e27374e3f639225ebe5cfed2e94f7e97d1293f9c91`.
Raw artifacts remain under ignored `runs/` paths; the evidence index
publishes accepted run IDs and every raw SHA-256. Twelve earlier `-probe-`
diagnostic runs established the expected notice-overrun classifier and are
excluded from acceptance and publication.

This panel documents native acceptance and the observed fixed-seed
outcomes. It does not prove a population law, full exponential tail,
independence, a universal delayed-start rule, other EXP parameters or
distribution families, GUI-only behavior, or cross-engine parity.
