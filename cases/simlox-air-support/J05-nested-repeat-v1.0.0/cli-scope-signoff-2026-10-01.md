# J05.var04 CLI scope sign-off — 2026-10-01

## Accepted boundary and source

`J05.var04` tests one nested `ResultCollectionProfile` subprofile repeated twice for `SYSTEM`, compared directly with the accepted J05.var03 profile. This is a single deterministic A01 mission, seed 1, `SIMPE=36`. It does not claim deeper hierarchies or general repeated-profile rules. The [contract](contract.json), [builder](build.py), [exact diff](exact-diff.json), and [author replay](review/author-validation-2026-10-01.json) bind the scope. The installed SIMLOX manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` (physical pages 230–231 and 532–537); dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0` (lines 689–702). Those proprietary sources remain local.

The A01 baseline input SHA-256 is `8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`. The accepted direct control is byte-identical to J05.var03's mixed input, SHA-256 `0eaa2c466e196f471bde4054f278bd018bae5f3eea2e15b9d0f21dba96223e38`. The nested child SHA-256 is `f14aadd297fb97cb5031726c6da6acf0060fe051c73a65ae271489369874c5f1`. It changes only the description, the SYSTEM `RCPID` reference, and the profile rows. `J05SEG` has `CONTINUOUS` at relative 0 for duration 0.5 with `RCINT=0.5`, then `SNAPSHOT` at relative 0.5. `J05TOP` references `J05SEG` at 7.75 with `IQTY=2`, `IINT=2`, expanding the segment to starts 7.75 and 9.75. Global snapshot times remain 6/14. The dictionary permits nonnegative `STIM`; the fresh native run resolved the manual's looser positive-time wording for this one zero-relative-start input.

## Native execution and raw seals

The [guarded native runner](run_native_ssh.ps1), SHA-256 `7f8eec17252a00e55b6861c0a4317373e287ef87613299ac20ac764f615cdaf9`, executed three fresh five-step runs through authenticated session-0 SSH under `Global\SimloxIssue18NativeQueue`, preserving GUI PID 13340. All import, export, calculation, JSON report, and exact-roundtrip checks exited zero. Source business rows roundtripped exactly for 13/16/16 populated tables; conversion reported **Errors: 0, Warnings: 2, Notes: 0** for each run. Warning #108 is enabled logging and #126 is the item-free teaching aircraft. The [roundtrip checker](check_roundtrip.py) SHA-256 is `84bd5f3f237c07673b1609c82680ef67f3001384380307b4dccb3ddc3194a95b`.

| Variant | Raw run ID | Closure SHA-256 | SXO SHA-256 |
|---|---|---|---|
| A01 baseline | `j05-nested-baseline-v100-20261001-01` | `1d8da9e5a15351d138269619d61048ef17dad86da18d9ec8694f3b3d839c3d8e` | `7f8c22887fe7422e7ff256ef249590ca0c94e01cf43c2fb7dbe5fa5fd84beb04` |
| Direct J05.var03 control | `j05-nested-direct-v100-20261001-01` | `73ddcb1aedab7f6639dfc38e7cf08fad78ee0d92c2d31c6fad17ba324cb8aa86` | `f9a4210a602838db928322af35ee1c9fd235e2653ca7daad648e99718e30df70` |
| Nested repeat | `j05-nested-repeat-v100-20261001-01` | `b54ba74fe2f3bc4ce10e5cd57aebf1f529e8c3c8342802ef6f29ee4df8d44613` | `7b345ed8d146d48747092ce3402837363ada05044cb321360b70d800ccc0924e` |

All three `model.log` files are byte-identical, SHA-256 `6337dc631e574eb9fab1eb24c45b4a3e1568d7e645282051c234a032591887ed`. The full event ledger shows mission order/allocation at 7, start at 8, task start 8.5, task completion 9.5, mission success and aircraft ready at 10, and day-one marker at 24. `ResultSummary` retains one replication, report range 0–36, `MTMF=MSTF=1`. Baseline System and all three Stock results have 72 half-hour bins; Stock has `PNB=1` and zero demand/backorders in every bin. Direct and nested System results each contain exactly two intervals: 7.75–8.25 has `NSYRY=0`, `NSYMA=1`, `NSYMO=0.5`, `STACC=0.5`; 9.75–10.25 has `NSYRY=0.5`, `NSYMA=0.5`, `NSYMO=0.5`, `STACC=0.5`. All non-description tables in the direct and nested default reports match by parsed rows.

The default JSON report omits replication snapshots. The [report-only runner](report_existing_sxo_ssh.ps1), SHA-256 `18475bff982689be975c971e88c1f91685b3e347be93cea59ebf69bbab6730c4`, used each sealed SXO and a local copy of the installed `Default.sxs` with only serialized `GeneralSettings.OUTRP` changed from `N` to `Y` at byte offset 67165. The installed file SHA-256 stayed `1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d`; the ignored local copy SHA-256 is `6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882`. The [settings builder](make_report_settings.py) SHA-256 is `4c1316193f29269807fd5ed96d55f53a0361e7e4f45a1669ca3bcd5287246dcf`.

| Report-only source | Raw run ID | Closure SHA-256 | Report SHA-256 |
|---|---|---|---|
| Direct control | `j05-nested-direct-report-v100-20261001-01` | `b6349f6cbede829609acb4356393c35a9d045328ab9ff4e3d711f71d3c06cd40` | `14d78f6f9e87b1fbd1c51b5ccb9a73072c409a0f7345624559178920aefeaa3c` |
| Nested repeat | `j05-nested-repeat-report-v100-20261001-01` | `71225284963aef63c2106a5ea104dd78690953cc5eb6bb5c8425e08618cbaa81` | `dc80b6566309f226e3d81f41ae96d9561ffaa8ca81791aa66cdd69c3b4e2fc20` |

Both enabled reports have identical non-description rows, including exactly two `SystemResultsReplicationSnapshot` rows for `TEACH-UNIT`/`TEACH-AIR-01`: at 8.25, ready 0, assigned 1, operating 1; at 10.25, ready 1, assigned 0, operating 0. This directly distinguishes the instantaneous snapshots from neighboring interval averages and shows override of global 6/14. The source SXO files were not recalculated by the report-only pass. All raw files and the local `.sxs` copy stay in ignored `runs/` and are not uploaded.

## Replay and limits

Author [validator](validate.py), SHA-256 `f3286250948843247af454a7f94785af3d36fa1f8a084b9436d0f35052f37195`, passed 62/62 checks; its [report](review/author-validation-2026-10-01.json) SHA-256 is `c95d8f9ef37385623c08c0450c2af81edd4d38f2a3e3b6ce93f1264670149a47`. An independent [read-only replay](review/independent_readonly.py), SHA-256 `6d4bba8ea583568983a6b4c2c7a5dc98e48ebec31159637199af1f49ba976a6a`, passed **74/74** checks without importing author code or invoking SIMLOX. Its [report](review/independent-readonly-2026-10-01.json) SHA-256 is `9ec6007e7ac9d43679eb2121647375da275618dc646aec2628a2cd3fe93eca68`. The reviewer independently checked the pinned manual/dictionary bytes, source and raw seals, guarded execution, exact row roundtrip, conversion, event and stock ledgers, two System bins, snapshot rows, and direct/nested result equality. Decision: **GO_BOUNDED**.

This evidence covers one seed, one deterministic mission, one subprofile containing continuous and snapshot rows, and two nonoverlapping repetitions. Deeper nested hierarchy, overlap/rejection behavior, MISSION result intervals, other result types, GUI display and cross-engine equivalence remain unverified. Product `main` is outside this scope.
