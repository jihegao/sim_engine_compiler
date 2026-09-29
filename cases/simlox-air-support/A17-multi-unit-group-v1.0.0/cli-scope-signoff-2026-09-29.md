# A17 1.0.0: two explicit units in one group, CLI scope sign-off

## Decision and source

`native_behavior_accepted_cli_scope` and `reusable_published` for **one
scheduled two-aircraft mission served by two explicit units at separate
bases under one UnitGroup**. The frozen [input](native-input.json), SHA-256
`66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974`,
derives from the [published A03 1.0.1 formation case](../A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md),
parent input SHA-256
`d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`.
The [frozen contract](contract.json), SHA-256
`c45b6b8dc4e77848e1243217225f053926aa29d9e8c0815f0dbd32da75bcec4e`,
declares the seven-table delta, hand timeline, manual sources and exclusions.
The source manual is the installed SIMLOX 2017 reference, SHA-256
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`;
its explicit-unit and UnitGroup fields on physical PDF pages 178, 184–185,
196 and 308–314 motivated the model. The proprietary PDF is not included.

## Sealed native evidence

Run ID `a17-v100-ssh-20260929-01` remains under the local ignored `runs/`
directory. The [four-step runner](run_native_ssh.ps1), SHA-256
`3baae928802b30a005f865a24644474abdfc40ad2132dbb6a0e31947052d1b74`,
ran import, export, calculation and JSON report export through session-0 SSH
under the host-wide native queue. All four commands exited zero, the pinned
SIMLOX executable SHA-256 was
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`,
and the runner preserved the existing GUI PID 13340, session 1 and process
start identity at each step. The invocation SHA-256 is
`286177cf998911c3e3519fa5c2a868ad73a479556204fdeb754dd94c1987ee6c`;
the raw closure SHA-256 is
`f1885aa1c21bf2260d1d7671e762d18451d91a0fc0398cf45309574d16c2f76b`.
The SXI SHA-256 is
`6546f0eaa60972c6aa50ffdb73a9b6ee161981ea8dbee0a454bda3fed9124f8a`,
the model log SHA-256 is
`ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e`,
and the raw report SHA-256 is
`fcd289233082398dfa8531475719a6b068dadc841486d050ec71f6815356a8f4`.

The import/export round trip preserved the 12 nonblank business tables and
three source tables containing only null placeholder rows; SIMLOX generated
18 other populated built-in default tables on export. Conversion reported
zero errors and only warning 108 (verbose simulation log) and 126 (the
teaching aircraft has no items). The log shows `TEACH-GROUP` ordering one
mission at hour 7, allocating aircraft `<TEACH-AIR-01,0>` from `TEACH-UNIT`
at `BASE-01` and `<TEACH-AIR-01,1>` from `TEACH-UNIT-2` at `BASE-02`, launching
the formation at hour 8, succeeding and returning each aircraft to its
original unit at hour 10. The report has one successful repetition, 72
half-hour intervals over 36 hours, two mission-hours, four aircraft-hours
and two aircraft ready at the end. The two sorties are established by the
joint launch/completion log; the exported SystemResults are aggregate rows.

The [author validator](validate_native_cli.py), SHA-256
`a1967651400b91fdf315ff84b8ac6e2d67217dcb1ce74101fbe175de25437cb4`,
passed 281 source-bound checks; its [result](review/author-validation-2026-09-29.json)
has SHA-256
`a75b361b9a74be465af75e09f2687c21eb2f116a3d759d22104e36661e48d5ae`.
The separate [read-only review](review/independent_readonly.py), SHA-256
`b0e08aec9c3631bd3359afb2c055bbaf7b73195c41db3596741889a060d60fc8`,
imports no author validator and recomputed the parent delta, raw hashes,
business-row equality, process provenance, events and report metrics. Its
[result](review/independent-readonly-2026-09-29.json), SHA-256
`1f20af7be347b5d52cffda50282a6f993b7cf949654e8dcbe9bc4413cffb4b4f`,
passed with `differences=[]`.

## Earlier probe and scope limits

The immutable import/export probe `a17-v100-schema-probe-20260929-04` has a
failed checker verdict because its first checker incorrectly required exact
populated-table-name equality. The native-added defaults explain the mismatch;
a corrected checker replayed its raw files read-only. The original closure
was not changed. The [preflight record](preflight-2026-09-29.md) retains
earlier disconnected-session and helper failures. None of those attempts
was counted as a behavior pass.

This decision covers only the frozen two-unit, two-aircraft one-wave recipe.
Both units are necessary, so priority choice is not tested. Implicit units,
equal-priority cycling, UNPR1 ordering, XTIME effects, symmetric station
groups, aircraft transfer, direct-to-group deployment rejection, GUI-only
behavior and cross-engine equivalence remain unverified. The two bases show
organizational membership; no geographic movement is inferred. GUI process
preservation is evidenced, while GUI calculation content was not reviewed
for A17. The contract and run's original `not_published` labels describe
their creation-time state; this dated sign-off records the bounded
publication decision.
