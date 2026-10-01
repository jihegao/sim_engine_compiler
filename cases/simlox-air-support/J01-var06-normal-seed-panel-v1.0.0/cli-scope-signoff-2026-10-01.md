# J01.var06 normal preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for twelve fixed-seed,
one-repetition native runs of the B01-derived preparation model. Reusable
publication requires merge to `simlox/main`. This does not complete J01 or
Issue #18.

The accepted `J01.var01@1.0.0` parent input SHA-256 is
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`.
The frozen [panel diff](panel-diff.json) SHA-256 is
`0dbeb7edca193e5e0bfbcac4032e53734d73f8b46ded04c6dc61720fc06d9569`.
Relative to that parent, seed 01 changes only `MissionPreparation.DURND`
`PREP-DET`→`PREP-NRM` and one `TimeDistributions` row to `PREP-NRM`,
`PFAC=1`, `<NORMAL>`, `PARAM1=0.5` mean and `PARAM2=1.0` standard deviation.
`PARAM3` stays empty and mandatory `DURN=0.5` hour remains. Seeds 02–12
differ from seed 01 only in `Control.RSEED`; all retain `NREPS=1`, one
aircraft and one scheduled mission.

The installed database dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`;
manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
Manual pp. 542–545 define the `<NORMAL>` mean, standard deviation and
zero lower boundary; the installed dictionary lists `<NORMAL>`. Native
import/export accepted and retained it in all twelve runs.

All twelve [indexed](evidence-index.json) runs used guarded session-0 SSH,
the host-wide Issue #18 mutex, and preserved GUI PID 13340/session 1/start
identity. Each import, export, calculation and JSON report completed;
converter errors were zero with the known #108/#126 warnings. Each of the
16 source tables with rows roundtripped exactly. Every run has one
preparation starting at hour 7, one successful mission, 72 System and
Stock half-hour bins, two integrated flight hours, and a ready aircraft
at the horizon. Event preparation durations reconcile with report hours.

The twelve logged draws range from zero to 1.27234 hour, with mean
0.50813 hour, sample standard deviation 0.52616 hour and nine distinct
values. Seeds 01/04/06/09 have exactly zero duration. Seeds 05/08/10
exceed the one-hour notice, launch at preparation completion, and succeed
about two hours later. The [author panel replay](review/author-panel-validation-2026-10-01.json)
passed with 132 sealed raw artifacts. The
[independent read-only replay](review/independent-readonly-2026-10-01.json)
passed 19,459 checks with zero failures; its report-integrated range is
0–1.272344381 hour and mean 0.508132038 hour. Independent script SHA-256
is `7ede36c8fae3ff7912d5142121221a13701e71e55ddd6158d15360ef8cea8527`;
verdict SHA-256 is
`3d45844956ebfbbdeeffcde2b143492e24b83580f1fb95081f3ff2113519e655`.
Raw artifacts remain under ignored `runs/` paths; the evidence index
publishes accepted run IDs and every raw SHA-256. Twelve earlier `-probe-`
diagnostic runs are excluded from acceptance and publication.

Exact zeros and nonnegative observations are consistent with the manual's
lower-bound description but do not identify the generator algorithm.
This panel does not prove a population law, full tail, independence,
universal delayed-start behavior, other NORMAL parameters or J01 variants,
GUI-only behavior, or cross-engine parity.
