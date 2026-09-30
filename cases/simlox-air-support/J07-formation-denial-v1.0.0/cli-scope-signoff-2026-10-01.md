# J07.var01–02 fixed-demand formation metrics: CLI scope sign-off (2026-10-01)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for a bounded fixed-seed `J07.var01–02` comparison. This is one single-aircraft control, one accepted-parent two-aircraft formation control, and one two-aircraft formation followed by a scheduled three-aircraft demand that cannot launch. The evidence supports the four global fixed-demand ratios in this one setup. It does not establish the entire J07 case or all its planned variants.

## Source and frozen model

The [A01 single control](single-control-input.json) SHA-256 is `8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`, byte-identical to accepted `A01.normal.1.0.0`. The [A03 formation control](formation-control-input.json) SHA-256 is `d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`, byte-identical to accepted `A03.formation.1.0.1`. The [denied-demand input](denied-demand-input.json) SHA-256 is `09bc55982f4623549880899687b79a17816a858e1a92663fa9cb2cf07420fbba`. Relative to A03 it appends `MissionType.THREE-AIR-DEMAND` with `NOS=MNOS=3`, appends a `SCHEDULED` `OperationProfile` row at `STIM=12` with `IQTY=1` and the same `DTIM=1/3`, and changes the description. All 28 other tables remain identical; the [exact diff](exact-diff.json) SHA-256 is `1c56dd4c450aff09eb65894a49afdacd9e7516d92411166ca7df8feb17218373`. Deployment remains two aircraft. The pre-run [contract](contract.json) SHA-256 is `3a4d4471e4606ff3ef4abcaad919278a0b13905cc2547665aeedd0203b00946e`.

The installed SIMLOX manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical PDF pages 551–553, 562, 566 and 568, defines mission time, system time, start and success factors. The installed dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`, lines 447–454 and 473–481, identifies the mission type and operation profile fields. These proprietary sources are not uploaded. The installed `Simlox.exe` SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

## Sealed native triplet

Three fresh, serial, authenticated session-0 SSH native runs used the host-wide `Global\SimloxIssue18NativeQueue` mutex and verified GUI PID 13340 in session 1 before and after each step. The import, export, calculation, JSON report and source-roundtrip check all exited zero. Every one of the 13 row-containing source tables roundtripped exactly. Input conversion recorded zero errors and two inherited warnings: #108 for enabled event logging and #126 for an aircraft with no modeled items. Native JSON trailing commas are removed only in parser copies. The raw run files remain immutable in ignored local `runs/` directories and each `closure.json` seals its invocation, input, model, report, logs, steps, and source fingerprints.

| Variant / run ID | `invocation.json` SHA-256 | `closure.json` SHA-256 | `report-raw.json` SHA-256 | `model.log` SHA-256 |
| --- | --- | --- | --- | --- |
| `j07-single-control-v100-20261001-01` | `176aeea3c4a21e127d2c16993f40fa1164c8f97a5f63541ee0a3d474690f96be` | `1fbc4f0e0746e688ca2f488aab7bb6ddaa2b08e43043e350953e8285281a64f7` | `b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099` | `6337dc631e574eb9fab1eb24c45b4a3e1568d7e645282051c234a032591887ed` |
| `j07-formation-control-v100-20261001-01` | `0153e7682fdcfea159d6968ebab6f0339bf4e30718693be6f0e1fa947a3335ec` | `ef6d9e454b43f5b1078a5b3892ee4980c16b60321c367210430e1f8f9bba8c25` | `8ff915b97b22720da95698f111697400a6d7bf9069232a73c50f6743668d9e28` | `5a88edd86e6fe3dfab96cb9fee12c7d327e9fe56b202be9c4f58918b06476809` |
| `j07-denied-demand-v100-20261001-01` | `ac250e4c13d55f6faf70b2eb1b535bfb4c5a6c43ec561efe390df50307dde658` | `c20341f4291c356c52f5de25827ad917eb8dc069ffc92079a34276d9ab04a273` | `c0451a18c667a213e8a9735e900e5b2812e45d6dc3aaa7f8e78f639a59403eb0` | `df35e558ec22d3c2b307eb7059d552a07859c769e2e8112cb72c36d3d99b1383` |

## Event, system, stock and metric ledgers

The A01 control orders at 7, starts at 8, and succeeds and completes at 10 using one aircraft. The A03 control has the same single mission timeline with two aircraft assigned to one formation. The denied child reproduces that first wave. It then orders `THREE-AIR-DEMAND` at 11 for a requested start at 12. Two aircraft allocate and prepare, but the mission waits for a third and is cancelled at 12.3333. It never starts, reaches no success point, and contributes zero operation hours. Both temporarily assigned aircraft complete turnround and return ready at 12.3333. The final 35.5–36 System bin has two ready aircraft and zero assigned, operating, failed or maintenance aircraft. The model log reaches the day-1 marker at 24; all runs finish at `SIMPE=36`.

| Run | Planned fixed missions | Started / successful missions | Aircraft sorties | Accomplished / prescribed mission hours | Accomplished / requested aircraft operation hours | `MTMF` | `MSTF` | `MSUF` | `STMF` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Single control | 1 | 1 / 1 | 1 | 2 / 2 | 2 / 2 | 1 | 1 | 1 | 1 |
| Formation control | 1 | 1 / 1 | 2 | 2 / 2 | 4 / 4 | 1 | 1 | 1 | 1 |
| Denied demand | 2 | 1 / 1 | 2 | 2 / 4 | 4 / 10 | 0.5 | 0.5 | 0.5 | 0.40000000596 |

Each `SystemResults` table has 72 half-hour bins from 0 to 36. The control exposures from interval averages are 33 ready, 3 assigned and 2 operating aircraft-hours for the one-aircraft run, and 66 ready, 6 assigned and 4 operating aircraft-hours for the two-aircraft control. In the denied child, the two aircraft add assigned exposure from 11 to 12⅓ without flying: 63⅓ ready, 8⅔ assigned and 4 operating aircraft-hours. Every interval, including the partial 12–12.5 bin, agrees with the event timing within native float precision. `StockTotalResults` has 72 matching bins with `PNB=1`, zero demands/backorders and no stock items modeled; no inventory effect is attributed to the cancellation.

The [author validator](validate.py) SHA-256 `2fc42cb15cf74538b1d02aefe6152ebefdf0ca11d44205c138390383a935673d` passes [44/44 checks](review/author-validation-2026-10-01.json), report SHA-256 `ea2b6da0839c0315d80663d43d558022878a5d7af2521bce3775618f1c198f7a`.

A separately written [independent read-only verifier](review/independent_readonly.py) SHA-256 `e711de5722aea8dcc2ae935768fa4119ae39cf5ed2bece303dd3297b01b12aa7` passes [74/74 checks](review/independent-readonly-2026-10-01.json), report SHA-256 `33baf2da6bbadb25e94550c9036751f13e759721ac2154e3f57b02157d21cbf2`. It reads the original native runs and accepted parents without importing the author validator or invoking SIMLOX. Its `bounded_go` decision independently confirms the fixed-demand denominator calculation and all 72 System and Stock bins per run.

## Scope limits

The CLI JSON report exposes `ResultSummary`, `SystemResults` and `StockTotalResults`, with no separate mission-level result table in these runs. The global ratios are checked against source planned demand plus the event and aircraft interval ledgers. This one fixed seed and two demand types does not establish partial-success `J07.var03`, success point before completion `J07.var04`, unit/group/type aggregation `J07.var05`, regenerative mission denominator exclusion, a stochastic or faulted mission, GUI display, or cross-engine equivalence. Issue #18 remains open.
