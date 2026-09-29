# D01 1.0.0: system-level direct repair, restricted CLI sign-off

## Decision and source

`native_behavior_accepted_cli_scope` and `reusable_published` **only for
the single-aircraft system-level direct-repair recipe** below. This is a
restricted first D01 slice, not acceptance of the catalog's installed-item
failure, item replacement or ItemRepair scope. It derives from the
[published A02 repeated-mission case](../A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md),
parent input SHA-256
`84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
The frozen [D01 input](native-input.json), SHA-256
`d418c811f2e1a9ad047af19038a3d0881d404adf0919d2e52dab70e6100ee450`,
changes only `ProblemDescription`, `System.FRT` and `SystemRepair`; the
[parent diff](parent-diff.json) lists every changed row. The frozen
[contract](contract.json) SHA-256 is
`3058fb0e29e3bb89449485b94ab92b372affd80660bb997a22d30d30816394eb`.

The installed SIMLOX 2017 manual, SHA-256
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`,
describes operational FRT as failures per million OPIDs on physical PDF
pages 240, 246 and 258; `System.FRT=300000` with `OPID=OPHOURS` therefore
specifies 0.3 failures per operating hour. Pages 190–191 and 211–212
describe traditional critical direct system failures and repair tasks;
pages 349–354 define `SystemRepair` at a workstation and `DIRPT` as total
turnaround time. No proprietary manual page is stored in the repository.

## Sealed native behavior

The four-step session-0 SSH run `d01-v100-ssh-20260929-01` remains in the
case's local ignored `runs/` directory. The [runner](run_native_ssh.ps1),
SHA-256 `07a152c54e72da4fd024839bb98037f3f5c282c7eebecc5e6ca317fbcc389a70`,
serialized the native calls under the host-wide queue and preserved GUI
PID 13340, session 1 and its start identity. All import, export,
calculation and report-export steps exited zero. The invocation SHA-256 is
`cad80021f770db3acb7af5f64a029f8af24b2aa44d41f439685f7e052405c8c4`;
the raw closure SHA-256 is
`c3769da04ae3e8e754ff172cb0bed9317a0ec7ec5352913086341cc0ad489c05`.
The SXI SHA-256 is
`ff465ca4b4ab1f0f9a61a32ea0c7121c8c87cf7547c8a2d36d70c72eb44294dc`,
the event log SHA-256 is
`71c46a192990c81bf27ed6fd1b41ea15b5ada25834131a7700d4d1b779e83161`,
and the raw JSON report SHA-256 is
`cb21d4b6f7c3c35b8d42412e60bb6ca85d178b4ef6e9d61d71ca294ba94fc83a`.

All supplied rows survived native import/export; the extra rows are
SIMLOX-generated default table values. Conversion had zero errors and only
warnings 108 (logging) and 126 (system contains no installed items). The
fixed seed produced two **observed** critical failures at hours 9.8829 and
33.8602 on `<TEACH-AIR-01,0>`, aborting the 08:00 and 32:00 missions.
Each aircraft returned to `BASE-01` at hours 10 and 34, entered a local
system direct-repair task without resource demand, completed a 0.5-hour
turnaround at 10.5 and 34.5, and became ready again. The middle 20:00
mission completed successfully at 22:00. There was no cancellation.

The report has 72 half-hour SystemResults intervals, two failure counts,
two repair counts, two half-hour repair windows and one aircraft ready at
hour 36. Mission success fraction is approximately 1/3; the sealed
[A02 no-fault control](../A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md)
has 3/3 success, zero failures and zero repairs under the same three-wave
schedule. Its report SHA-256 is
`a7227687988841c074b28b524792af7d856cd674840169bf15c210f2d2cd4739`.
The six changed half-hour SystemResults rows begin at 9.5, 10, 10.5,
33.5, 34 and 34.5 hours. The coarse report still totals six nominal
mission-operation hours even though two missions aborted late; exact abort
times come from the event log, not that aggregate duration.

The [author validator](validate_native_cli.py), SHA-256
`bb29231b1aaf3a43054e6c345f2b4f3457c768ea4d31cca42bb517e74bcbb579`,
passed 293 source-bound checks; its [result](review/author-validation-2026-09-29.json)
SHA-256 is
`7f040f107675348511be04150a8ec9cbdd234d77bb01ee11269ccd6f00fdcae4`.
The separate [read-only reviewer](review/independent_readonly.py), SHA-256
`72df60b990fcaa8361dfefd974e2a1ca97a7103c4789bb155ef02c9f0c1fdca7`,
imports no author validator and replayed the raw seals, parent delta,
source bindings, process provenance, roundtrip, events and report against
the A02 control. Its [result](review/independent-readonly-2026-09-29.json),
SHA-256 `7198b785f80e2e6cb5db51940a237a87b097760169aae33aa186373b6ab4d4f0`,
passed with `differences=[]`.

## Restricted and unverified

The two failure times are run-specific observations for seed 1 and this
executable, not scheduled inputs or a portable random-stream guarantee.
`DIRPT=0.5 h` is total repair turnaround, not a separately measured wrench
time. There is no installed component in this model; item failure,
replacement, `ItemRepair`, stock and resupply remain unverified D01
extensions. No resource contention, PM, explicit failure mode, GUI-only
behavior or cross-engine equivalence is accepted. GUI preservation is
recorded by the bound runner; GUI window content was not sampled. The
original contract and native run say `not_published` because they were
created as a candidate; this dated sign-off is the restricted publication
decision.
