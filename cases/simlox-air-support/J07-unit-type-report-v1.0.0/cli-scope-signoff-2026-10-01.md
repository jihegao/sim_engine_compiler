# J07.var05 1.0.0: bounded CLI unit and type reporting sign-off

## Decision and lineage

`native_behavior_accepted_cli_scope`, `reusable_published` **only for the unit and mission-type reporting slice** in this package. The [pre-run contract](contract.json), SHA-256 `08011f423ef7c16b21d85f959efb9d132e738a56cbc8a64db26d6e0e903f2875`, explicitly excludes a rollup of member-unit missions into a `UnitGroup` row. This remains an open part of J07.var05. A prior local candidate that required such a group row received independent NO-GO; the fresh run under this narrower contract repeats that negative selector as a control rather than upgrading the failed claim.

The parent is the accepted A17 two-unit group case, source SHA-256 `66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974`. The child [input](native-input.json) is SHA-256 `5609881f54c47c024b1b41f338bf0dd0e04e20e49a41d42b1a81642bdab54f55`. [The exact diff](exact-diff.json) is SHA-256 `5bc4c023d9eef021cbfeb8ef717586867a633d3262a0d860e12eea9268b0824e` and changes only `MissionType`, `OperationProfile`, `Operations`, and `ProblemDescription`. Both one-aircraft units and their `TEACH-GROUP` membership remain. The two separate unit-owned fixed profiles each schedule a different one-aircraft mission at hour 8 for two hours. The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; its physical pages 546 and 560 describe report dimensions and mission results. The installed dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. Neither proprietary source is uploaded.

## Native evidence

Fresh run ID `j07-unit-type-v100-20261001-01` used the pinned SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`, authenticated session-0 SSH, host mutex `Global\SimloxIssue18NativeQueue` and the active GUI PID 13340 guard. The [runner](run_native_ssh.ps1) SHA-256 is `fbaac641785138202599a520798a870445a1d52fec5bffb115ff1c7967222a97`. Import, export, calculation, default JSON report and source checker all exited zero while the GUI identity stayed stable. All 15 populated source business tables roundtripped exactly. Conversion had zero errors and only warning #108 for logging and #126 for the itemless teaching aircraft. The raw native [closure](runs/j07-unit-type-v100-20261001-01/closure.json) SHA-256 is `aa789a393f6d03c0c61d13c6eb08962f1b9e25172528a3322cbd6c06d0738f42`; the SXO SHA-256 is `fd0ed37f117fcc497621a363407e6e96f36930a00b58c5e03ca038757b5dc445`. The model log SHA-256 is `a9435218c4092ecc0b55575c5619ffe5ebba38cf306c91e4090cfc0fed951648`, byte-identical to the earlier diagnostic's log. Raw artifacts remain local and ignored under `runs/`.

The native log orders `MISSION-A` at `TEACH-UNIT` and `MISSION-B` at `TEACH-UNIT-2` at hour 7. Aircraft instances 0 and 1 are allocated to their respective unit missions, both launch at hour 8, both succeed and complete at hour 10, and each returns ready at its original unit. These are two waves and two aircraft sorties. The default report has 72 half-hour System and Stock bins from 0 to 36. Two aircraft are operating during hours 8–10, all Stock bins have no backorders, and two aircraft are ready at the end. `ResultSummary` has `NREP=1`, horizon 0–36 and `MTMF=MSTF=MSUF=STMF=1`.

## Report dimensions and reconciliation

The default JSON report omits mission-detail tables. [The local settings builder](make_report_settings.py), SHA-256 `922366a5cd1e0a1aece9ff56a9688d43ebe92458f1d2c1d3fd94a9bdba44e7e3`, starts from the installed `Default.sxs` SHA-256 `1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d`. It enables six `MissionSettings` table flags and changes only length-prefixed selector strings in ignored local copies. The installed file is unchanged. [Child](report_existing_sxo_ssh.ps1) and [A17 control](report_group_parent_ssh.ps1) report-only runners have SHA-256 `638926b6cd6b4293f0e97c4811cc8089df6f1cb2bfb5b33ea6ecab465a2515df` and `84b858e47f1d84d6723bfe630ae272374c420f4ced543738eae5cf8323f04e02`. Every report export retained the SXO, settings, executable, default-settings and GUI guards; every report has an invocation and raw SHA-256 closure.

| Native `FixedMissionResultsTotal` selector | Requested/started/succeeded waves | Requested/accomplished mission-hours | Requested/accomplished aircraft-hours |
|---|---:|---:|---:|
| Child, all units and types | 2 / 2 / 2 | 4 / 4 | 4 / 4 |
| Child, `TEACH-UNIT` | 1 / 1 / 1 | 2 / 2 | 2 / 2 |
| Child, `TEACH-UNIT-2` | 1 / 1 / 1 | 2 / 2 | 2 / 2 |
| Child, `MISSION-A` | 1 / 1 / 1 | 2 / 2 | 2 / 2 |
| Child, `MISSION-B` | 1 / 1 / 1 | 2 / 2 | 2 / 2 |
| A17 group-owned control, `TEACH-GROUP` | 1 / 1 / 1 | 2 / 2 | 4 / 4 |

Both child unit rows and both child type rows add exactly to their respective all-unit row. The 72 `MissionResults` half-hour bins integrate to these same hours. `MissionResultsTotal.MTREQ/STREQ` are 36-hour normalized rates, not raw hour counts; the raw counts above come from `FixedMissionResultsTotal` and interval integration. Child `TEACH-GROUP` and group-plus-type selectors emitted **no mission-result tables**, although each guarded report completed. A17's `TEACH-GROUP` row appears when the group itself owns the profile, while A17's member-unit selectors have no mission rows. Group membership alone therefore produced no member-mission rollup in these two fixed models. This is a bounded observation, not a general impossibility claim.

The report-only run IDs and closure SHA-256 values are:

| Source/selector (`*-report-20261001-01`) | Closure SHA-256 |
|---|---|
| `j07-all` | `9d68bacff94dc1908798937706e16489466fc05ba4822ecaf1ca5b478fb5674d` |
| `j07-group` | `485ee7a02c4e7305eb38b92835f32f48dc1a5ebb8eb6a891b0c5da57b81912ed` |
| `j07-unit-a` | `850c70413bf148a389fe88ef6f3ee2de49828980e55cbcaca4c8b2c41ef8f2da` |
| `j07-unit-b` | `6fdad4c4d5212dfef8ee8bf5709e23391edec239c9d6805466f8a35182da3f2a` |
| `j07-type-a` | `770580a195ecd009bce0f30b42c18a4414250449943b70c8c52d0abd79f0ade7` |
| `j07-type-b` | `0f4d274db1100d0996a6baca330e45945f49a4436fc3d8d61ed9a40c66799c40` |
| `j07-group-type-a` | `84fa03777c20d7f9b0e94ddc42163ba20a1ea8fcd30b5eff5732e678b97a8139` |
| `j07-group-type-b` | `0c86cdafb59fcc4733b6c3fe1fcc7f26b49b27452f6a555be9841338bd430a1e` |
| `a17-all` | `2288189a8b5a7e67d14196d2f59e1ef50b28223ebd0376df3c0514dc30c78787` |
| `a17-group` | `6841bd6a37dc9c7b3340c94f6d80c011338e0b784a1449342d7583ea542cb128` |
| `a17-unit-a` | `1c4484cace675c8ef6b7c79dca399f5fdce15f70ba7ab8b6af90b36a4a0d659c` |
| `a17-unit-b` | `5c81f3a534adaa6998280d30c6ccc3738206e1d91fbc237d9f588d12a759e0eb` |

## Validation and limits

[Author read-only replay](validate.py), SHA-256 `b2d906bbebe7190e304959067488b9507621ca2ec7704a9af8a0c2afac4c27e0`, passed 886 checks; its [result](review/author-validation-2026-10-01.json) SHA-256 is `8a44a48a8e43ed3dd182efc8f59ccb0fbf0010e3f62525b5fe54f70d97003e3d`. The separate [independent reviewer](review/independent_readonly.py), SHA-256 `9cc4526d6f60ae203ccdcbe720e2b2951a73a90b85b221b3efbce5c6fc9ce03`, imported no author checker and made no native calls. Its [result](review/independent-readonly-2026-10-01.json), SHA-256 `debf5d243bba3d007f17eb8b48187b6c9b914789cd99ab81b67d6af63ccb0cb0`, passed 78/78 checks with bounded GO. The earlier broader group-rollup candidate independently received NO-GO. Neither decision licenses a full J07.var05 completion claim.

This one-seed CLI case has no failures, resource conflicts or varying schedule. Group aggregation of member-unit missions, regenerative denominator exclusion, mid-mission partial outcome, GUI result rendering and cross-engine behavior remain unverified. Issue #18 remains open.
