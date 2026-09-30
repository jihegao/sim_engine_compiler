# J05.var01–02 collection windows: CLI scope sign-off (2026-10-01)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed A01 mission and two bounded result-collection changes: a global `Control` window observed in `SystemResults` and `StockTotalResults`, and a `SYSTEM` `ResultCollection` override observed relative to Stock. This does not establish direct MISSION result intervals or the full J05 case.

## Source and frozen delta

Accepted [A01](../A01-single-aircraft-single-mission/native-input.json) and the byte-identical [baseline](baseline-input.json) have SHA-256 `8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`. [Global-window input](global-window-input.json) SHA-256 `e08a094aba3d0fe70c63aced459ea73ff582cdf8d1a61b5e52d22ed9bfaada15` changes `Control.RCINT` 0.5→0.25, `RCSTA` 0→7.5, `RCEND` 36→9, removes the optional MISSION and SYSTEM `ResultCollection` rows, and labels provenance. [SYSTEM override input](system-override-input.json) SHA-256 `28ad0e43701d4eba1276a391992b67495506afc9076e80065b583d0932d28f6d` adds only a `SYSTEM` row `[SYSTEM,0.5,0,36,null,null]` relative to that global input and changes its label. `SIMPE=36`, seed 1, mission schedule, aircraft and all mechanism tables remain identical. The [exact diff](exact-diff.json) SHA-256 is `304437842ad8fa847b2fae9b376642a2ca0b73db1d7dd8ded710ac1a64833f6c`; the pre-run [v1.0.1 contract](contract.json) SHA-256 is `a222d20750e413582bbed1c9f6f296434fc903d83a6656bfd91ee52061a7c5f2`.

The installed SIMLOX manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical PDF pages 230–231 and 532–533, distinguishes simulation period `SIMPE` from `RCINT`/`RCSTA`/`RCEND`, describes `Control` defaults and `ResultCollection` per-type overrides, and says state results are interval averages. The installed dictionary SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`, lines 137–143 and 689–694, identifies the corresponding fields. Neither proprietary source is uploaded.

## Sealed native triplet

Three fresh sequential runs used session-0 SSH with an `sshd.exe` ancestor, the host-wide `Global\SimloxIssue18NativeQueue` mutex, and GUI PID 13340/session-1 identity guards. Import, export, calculation, JSON report and source-roundtrip checks exited zero in every run. All 13/12/13 row-containing source business tables roundtripped exactly. Input conversion recorded zero errors and only warnings #108 (event log enabled) and #126 (teaching aircraft has no items). The installed executable SHA-256 was `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`. Native raw JSON trailing commas are normalized only in parser copies; raw files remain intact and locally sealed.

| Variant / run ID | `invocation.json` SHA-256 | `closure.json` SHA-256 | `report-raw.json` SHA-256 |
| --- | --- | --- | --- |
| `j05-baseline-v101-20261001-01` | `c9db149d16a886022ff156d254513d3368a7f4ae881d46cef09275ec381319c5` | `544ac02924741dae7f002b6bc3bb5c3002fe6b2d0f4a4cdd88088c5d5fd3c5ad` | `b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099` |
| `j05-global-window-v101-20261001-01` | `ce2b30e776fe0bfa51382076479a9dff4ed4900239220656762f0bff7cbc2cd6` | `60e61c577abc606351cff6a43ebfeefab2097b2e4c5acdc1cb01e5704c6b01cc` | `fbec39445325d21e1911ae102877ba6607b5851ecacf257e35aa1352bf146fa6` |
| `j05-system-override-v101-20261001-01` | `e5a1f6c9ea0138058d57784857ce946376642a5867a15c06002fdd26b4776586` | `799a21df7473d8908d4674304c6e4b8873529cd15a47d8f31dff7128902a1fb3` | `9e1ef10299e0344148e8b9b9be12375d931bb3a2972b6773c1f164301eed65a8` |

The three `model.log` files are byte-identical, SHA-256 `6337dc631e574eb9fab1eb24c45b4a3e1568d7e645282051c234a032591887ed`: aircraft allocated at 7, mission starts at 8, succeeds and returns ready at 10, and the day-1 marker appears at 24. `ResultSummary` is identical across the three reports with `NREP=1`, `RTILW=0`, `RTIUP=36`, and mission/system completion indicators equal to 1. This summary describes the full simulation; it is not limited to exported short-window bins.

| Variant | `SystemResults` | `StockTotalResults` | Integrated `NSYRY` / `NSYMA` / `NSYMO` / `STACC` hours within System bins |
| --- | --- | --- | --- |
| Baseline | 72 × 0.5 h, 0–36 | 72 × 0.5 h, 0–36 | 33 / 3 / 2 / 2 |
| Global window | 6 × 0.25 h, 7.5–9 | 6 × 0.25 h, 7.5–9 | 0 / 1.5 / 1 / 1 |
| SYSTEM override | 72 × 0.5 h, 0–36 | 6 × 0.25 h, 7.5–9 | 33 / 3 / 2 / 2 |

Every System bin matches the event timeline: ready during 0–7 and 10–36, mission assigned during 7–10, operating during 8–10. The stock rows have zero backorders/demands and `PNB=1`; no stock item is modeled. The override's System rows equal the baseline's exactly, while its Stock rows equal the global-window rows exactly. These rows show the `SYSTEM` override leaves the observed Stock output on the `Control` window. The global short-window `STACC=1` hour is an interval exposure, while the mission completes an hour after that window at 10.

The [author validator](validate.py) SHA-256 `4f3321989f8d7874a13cd7ca3154ba44ef1322845cebb94df6b53629a935b2ed` passes [44/44 checks](review/author-validation-2026-10-01.json), report SHA-256 `089b49d9498e17ff8c2dea1f142627a8658e3f9df0227da693295ce38594f95e`. A separately written [independent read-only verifier](review/independent_readonly.py) SHA-256 `691877f42860a14e2127078c0b5c5f9eb1f8847ce3a4952177588fdc8b96fd58` passes [69/69 checks](review/independent-readonly-2026-10-01.json), report SHA-256 `b60717829dee77230a023e2248f21e759a65e995da06f12f9249b0aee61ffab4`. The independent verifier does not import the author validator.

The v1.0.0 diagnostic triplet used the same inputs but required direct MISSION interval evidence. Its CLI report exposed no `MissionResults` table, so the original requirement was not met. Its frozen contract and runs remain local diagnostic material, excluded from this publication. The v1.0.1 contract narrowed the observable claim before the fresh runs. Direct MISSION window behavior, `ResultCollectionProfile`, `SNAPSHOT`, other result types, GUI display and cross-engine equivalence remain unverified. Issue #18 stays open.
