# J07.var03 nominal target shortfall: CLI scope sign-off (2026-10-01)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for a bounded fixed-seed `J07.var03` nominal-target shortfall. This triplet shows that one aircraft can fly and complete a mission whose nominal target is two when `MNOS=1`, while the same available aircraft cannot launch when `MNOS=2`. The mission is classified successful even though only half the nominal system operation time is delivered. This is one bounded meaning of “partial” for J07.var03, not a general partial-mission outcome rule or full J07 acceptance.

## Frozen A03 lineage and model delta

The [full control](full-control-input.json) is byte-identical to accepted `A03.formation.1.0.1`, SHA-256 `d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`. It has `MissionType.NOS=MNOS=2`, two deployed aircraft, and a two-hour mission scheduled at 8. The [strict shortage](strict-shortage-input.json) SHA-256 `b4074a56007fc989e20025932741d3dc40d7207f23b2c6908dfd10eff98c3a03` changes deployment quantity 2→1 and its label, retaining `NOS=MNOS=2`. The [partial minimum](partial-minimum-input.json) SHA-256 `90c89f8fa4fc7202d5b461a022a7219c0eae436aa842be410018dc16c96f17f6` has the same single aircraft and changes `MissionType.MNOS` 2→1 while `NOS=2` stays fixed. Seed, mission duration, success point, schedule, result windows and all support tables remain identical. The [exact parent diffs](exact-diffs.json) SHA-256 is `c2d9bee8323e1a347847e1ff1ca427c26d61678d4d852c0e8aa8258b78ad6d78`; the pre-run [contract](contract.json) SHA-256 is `06ffd36aecd4da435b293b7395ce35c0bd16a1a79689803480b2ac942006b08d`.

The installed SIMLOX manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical PDF pages 263–264, defines `NOS` as the nominal requested count and `MNOS` as the start minimum when fewer than `NOS` can be allocated; pages 552–553 define the global mission/system factors. The dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0` identifies the modeled fields. Installed `Simlox.exe` SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`. Proprietary sources are not uploaded.

## Sealed native triplet

Three fresh serial session-0 SSH runs held `Global\SimloxIssue18NativeQueue` and guarded GUI PID 13340/session 1. Import, export, calculation, JSON report and exact source-roundtrip checks exited zero in each run. All 13 row-containing source tables roundtripped exactly. Input conversion recorded zero errors; inherited warnings #108 (event log enabled) and #126 (teaching aircraft has no modeled items) were classified. Each local immutable `runs/` closure seals invocation, source/executable fingerprints, raw model, report, logs and step hashes; native JSON trailing commas are normalized only in parser copies.

| Variant / run ID | `invocation.json` SHA-256 | `closure.json` SHA-256 | `report-raw.json` SHA-256 | `model.log` SHA-256 |
| --- | --- | --- | --- | --- |
| `j07-full-form-control-v100-20261001-01` | `f1bac4b92e54a13619a6b1603018f94ef599cbc8f59d2c4ccc82c60f2e02ec2d` | `3fe567017d5e9adef5c3c60698757ad4138bcd15155fc080e77647a950e7e142` | `8ff915b97b22720da95698f111697400a6d7bf9069232a73c50f6743668d9e28` | `5a88edd86e6fe3dfab96cb9fee12c7d327e9fe56b202be9c4f58918b06476809` |
| `j07-strict-shortage-v100-20261001-01` | `9720cc8532a23e0356e19877269298e1b0a4d606d64710abdbf1d495a783844c` | `6c0a7d3beb684c11c69bb18df2378e464af4d6902aebd3909afaf482c0b4f96f` | `56c81d7d57452acef2d10947a82fc6f42deebfe0f85c269a701e435e32973754` | `bd3caad8ea86da0a7402ad6beeac3cc548c3e86d2b66d5a4b058417f86ded506` |
| `j07-partial-minimum-v100-20261001-01` | `0a18ac1db702c4f10773bcfe93bace6f1e3dd6bbc2caecb1acc4f24f337b49a1` | `592134e185a2d6e2544f18fb6729dc105db4d9dd712fd6d95df836984e857d1a` | `ddbb3538e2d734483151e346b7de6c6a4457df39e09ca5eb5e59fe7174d266ce` | `ad9076e1cb3e71e654c8aee3ebd77d7034737914f79262cff95c0e00e91aba43` |

## Wave, aircraft and factor ledgers

All three runs order one `BASIC-MISSION` at 7 and request two aircraft. The full control allocates two, starts a single formation wave at 8, and succeeds and completes at 10 with both aircraft; this is **one wave and two aircraft sorties**. The strict shortage allocates the only aircraft at 7, waits for a second until 8.33333, then cancels without launching. The partial minimum allocates one, starts at 8, succeeds and completes at 10 with that aircraft; this is **one wave and one sortie**. The strict temporary allocation contributes 1⅓ assigned aircraft-hours but no operation hours or sortie.

| Run | Nominal / minimum / deployed | Started / successful waves | Aircraft sorties | Accomplished / prescribed mission hours | Accomplished / nominal aircraft hours | `MTMF` | `MSTF` | `MSUF` | `STMF` |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full control | 2 / 2 / 2 | 1 / 1 | 2 | 2 / 2 | 4 / 4 | 1 | 1 | 1 | 1 |
| Strict shortage | 2 / 2 / 1 | 0 / 0 | 0 | 0 / 2 | 0 / 4 | 0 | 0 | 0 | 0 |
| Partial minimum | 2 / 1 / 1 | 1 / 1 | 1 | 2 / 2 | 2 / 4 | 1 | 1 | 1 | 0.5 |

Each `SystemResults` and `StockTotalResults` table has 72 half-hour bins over 0–36. Interval-average System states integrate to **66 ready / 6 assigned / 4 operating** aircraft-hours for the full control, **34⅔ ready / 1⅓ assigned / 0 operating** for strict shortage, and **33 ready / 3 assigned / 2 operating** for the partial minimum. Every bin, including strict cancellation within 8–8.5, matches the event timeline within native float precision. Failure, repair and PM fields remain zero; the final System bin has two ready aircraft in full control and one in each one-aircraft run, with none assigned or operating. Every Stock row has `PNB=1` and zero demand/backorder quantities; there is no modeled inventory effect.

The [author validator](validate.py) SHA-256 `b2c40b388d83251996af1c88741026ca02b6143880aee942fe9d8af9b5ab3132` passes [45/45 checks](review/author-validation-2026-10-01.json), report SHA-256 `8c449415a0870580f1a3246d229192412526a8e1072ed8f4b3ab7bd789408b97`.

A separately written [independent read-only verifier](review/independent_readonly.py) SHA-256 `130ab44a2410729e80e8d3dcd09a4ca01594dc5c237ee0653277052e4097785b` passes [65/65 checks](review/independent-readonly-2026-10-01.json), report SHA-256 `15a41f10d02589a99ae375601150a469dafec5963d1dbfe3016a283504df9121`. It replays the accepted lineage, all source and raw SHA seals, mission and aircraft ledgers, every System and Stock bin, native factors and terminal states without importing the author validator or calling SIMLOX. Its `bounded_go` excludes mid-mission partial-outcome and general formation claims.

## Scope limits

This tests a nominal formation target shortfall permitted at mission start. The one-aircraft mission itself completes and is fully successful by the native mission criterion; no mid-mission aircraft loss or partly completed mission is claimed. The setup has one seed, unit and unfaulted two-hour mission, with no support-resource competition. J07.var05 unit/group/type aggregation, regenerative denominator exclusion, mid-mission partial outcomes, GUI display and cross-engine behavior remain unverified. The separate J07.var04 publication covers only a success-point result classification after abort. Issue #18 stays open.
