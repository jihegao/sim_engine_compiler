# J01.var05 lognormal preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for twelve fixed-seed,
one-repetition native runs of the B01-derived preparation model. Reusable
publication requires merge to `simlox/main`. This does not complete J01 or
Issue #18.

The accepted `J01.var01@1.0.0` parent input SHA-256 is
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`.
The frozen [panel diff](panel-diff.json) SHA-256 is
`6d77167fcaae05d68cc29533ae7698c78e1157c7e6a6ff71299868e9eb1f02b6`.
Relative to that parent, seed 01 changes only `MissionPreparation.DURND`
`PREP-DET`→`PREP-LGN` and one `TimeDistributions` row to `PREP-LGN`,
`PFAC=1`, `<LOGNORM>`, `PARAM1=0.5` location and `PARAM2=0.25` scale.
`PARAM3` stays empty and mandatory `DURN=0.5` hour remains. Seeds 02–12
differ from seed 01 only in `Control.RSEED`; all retain `NREPS=1`, one
aircraft and one scheduled mission.

The installed database dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`;
manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
Manual pp. 543–545 spell `<LOGNORMAL>` and assign `PARAM1`/`PARAM2`
to location/scale; the installed dictionary lists `<LOGNORM>`. Native
import/export accepted and retained `<LOGNORM>` in all twelve runs.
The location parameter is not asserted to be the preparation mean.

All twelve [indexed](evidence-index.json) runs used guarded session-0 SSH,
the host-wide Issue #18 mutex, and preserved GUI PID 13340/session 1/start
identity. Each import, export, calculation and JSON report completed;
converter errors were zero with the known #108/#126 warnings. Each of the
16 source tables with rows roundtripped exactly. Every run has one positive
preparation starting at hour 7, a successful mission from hour 8 to 10,
72 System and Stock half-hour bins, two integrated flight hours, and a
ready aircraft at the horizon. Event preparation durations reconcile with
report preparation hours. No draw exceeded the one-hour notice in this
fixed panel.

The twelve logged draws range from 0.28921 to 0.58783 hour, with mean
0.46531 hour, sample standard deviation 0.09790 hour and twelve distinct
values. The [author panel replay](review/author-panel-validation-2026-10-01.json)
passed with 132 sealed raw artifacts. The
[independent read-only replay](review/independent-readonly-2026-10-01.json)
passed 19,458 checks with zero failures; its report-integrated range is
0.289206–0.587834 hour and mean 0.465307 hour. Independent script SHA-256
is `746276767866d1d118371e204e6f6fe6a6998c7cedc75307337cdbb849aeb59b`;
verdict SHA-256 is
`3b97ed9afb298ca711a8cab6662fe3993b877000c94f5513b1aba8369380b1d5`.
Raw artifacts remain under ignored `runs/` paths; the evidence index
publishes accepted run IDs and every raw SHA-256. Twelve earlier `-probe-`
diagnostic runs are excluded from acceptance and publication.

This panel documents native acceptance and the observed fixed-seed
outcomes. It does not prove a population law or mean, full tail,
independence, a general lack of notice overrun, other LOGNORM parameters
or distribution families, GUI-only behavior, or cross-engine parity.
