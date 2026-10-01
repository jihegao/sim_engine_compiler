# J01.var07 GAMMA preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for twelve fixed-seed,
one-repetition native runs of the B01-derived preparation model. Reusable
publication requires merge to `simlox/main`. This does not complete J01 or
Issue #18.

The accepted `J01.var01@1.0.0` parent input SHA-256 is
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`.
The frozen [panel diff](panel-diff.json) SHA-256 is
`c70937d42d43be5b48a96f3dcb32ba859be7c93b52894c2cb7e2499a1c8649a8`.
Relative to that parent, seed 01 changes only `MissionPreparation.DURND`
`PREP-DET`→`PREP-GAM` and one `TimeDistributions` row to `PREP-GAM`,
`PFAC=1`, `<GAMMA>`, `PARAM1=2` (`n`) and `PARAM2=0.5` (`Beta`). `PARAM3`
stays empty and mandatory `DURN=0.5` hour remains. Seeds 02–12 differ
from seed 01 only in `Control.RSEED`; all retain `NREPS=1`, one aircraft
and one scheduled mission.

The installed database dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`;
manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
Manual pp. 542–545 name `<GAMMA>` and its `n` and `Beta` fields; the
installed dictionary lists `<GAMMA>`. Native import/export accepted and
retained the row in all twelve runs.

All twelve [indexed](evidence-index.json) runs used guarded session-0 SSH,
the host-wide Issue #18 mutex, and preserved GUI PID 13340/session 1/start
identity. Each import, export, calculation and JSON report completed;
converter errors were zero with the known #108/#126 warnings. Each of the
16 source tables with rows roundtripped exactly. Every run has one positive
preparation starting at hour 7, a successful mission from hour 8 to 10,
72 System and Stock half-hour bins, two integrated flight hours, and a
ready aircraft at the horizon. Event preparation durations reconcile
with report preparation hours.

The twelve logged draws range from 0.05482 to 0.70391 hour, with mean
0.403065 hour, sample standard deviation 0.242164 hour and twelve
distinct values. None exceeds the one-hour notice in this fixed panel.
The [author panel replay](review/author-panel-validation-2026-10-01.json)
passed with 132 sealed raw artifacts. The
[independent read-only replay](review/independent-readonly-2026-10-01.json)
passed 19,458 checks with zero failures; its report-integrated range is
0.054817092–0.703907594 hour and mean 0.403065029 hour. Independent
script SHA-256 is
`0763ec9b4d63cc6f8075e908dd63e43af2ea80b4844f5503c4e0238d61de5f5c`;
verdict SHA-256 is
`51635d862c825aba2168528f9ecbe71da90277873cffbc86bee3fb207c63b120`.
Raw artifacts remain under ignored `runs/` paths; the evidence index
publishes accepted run IDs and every raw SHA-256. Sixteen earlier
`-probe-` diagnostic runs are excluded from acceptance and publication.

This panel documents native acceptance and observed fixed-seed outcomes.
It does not prove the population law, full tail, independence, general
`n`/`Beta` parameter semantics, a general lack of notice overrun,
other J01 variants, GUI-only behavior, or cross-engine parity.
