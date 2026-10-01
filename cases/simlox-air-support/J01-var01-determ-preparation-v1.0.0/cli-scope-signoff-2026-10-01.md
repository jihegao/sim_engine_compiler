# J01.var01 deterministic preparation: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for one B01-derived fixed-seed
mission preparation using `TimeDistributions.PREP-DET`. Reusable publication
requires merge to `simlox/main`; this does not complete J01 or Issue #18.

The accepted B01 input SHA-256 is
`2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b`.
The child input is
`b7e8e737e8ad9c0ce4700f6b7a9b7fcfe9b332100210793977b2230f4dca4409`,
and the exact parent diff is
`93aaa6f81dc9e44a463969463b01970fb8d2e4b170caa88b2b20d0c9eb1098f7`.
Only `MissionPreparation.DURND` changes from null to `PREP-DET`, and one
`TimeDistributions` row adds `PREP-DET`, `PFAC=1`, `BASED=<DETERM>`,
`PARAM1=0.5` hour. The mandatory `DURN=0.5` remains. The installed manual
SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`;
manual pages 510–511 and 543–545 plus the pinned dictionary support this
model. B01 has no preparation subtasks that would override `DURND`.

Fresh guarded session-0 SSH run `j01-var01-determ-probe-20261001-02` completed
import, export, calculation and JSON report under the host-wide Issue #18
mutex. GUI PID 13340/session 1/start identity remained intact. Native
conversion had zero errors and the known warnings #108/#126. The exact
roundtrip retained all 16 source tables with rows, including 13 with nonempty
business values; the distribution row and `DURND` reference are unchanged.
One preparation started at hour 7, ended at 7.5, and was followed by the
hour 8–10 successful mission. The 72 half-hour SystemResults bins reconcile
0.5 preparation aircraft-hour.

The run closure seals 11 raw artifacts and 9 post-run source hashes. The
[author replay](review/author-validation-2026-10-01.json) passed, and the
[independent read-only replay](review/independent-readonly-2026-10-01.json)
passed 1,633 checks with no failures. The first non-PTY SSH preflight (`-01`)
stalled before creating a run directory or starting native SIMLOX and was
stopped; it supplies no behavior evidence. The accepted `-02` raw run remains
under ignored `runs/` and is bound by [evidence-index.json](evidence-index.json).

This one fixed-seed observation verifies a native deterministic distribution
reference for the B01 workload. It does not establish a statistical sampling
law, other distribution families or parameters, GUI behavior, or cross-engine
equivalence.
