# J07 1.0.0: bounded fixed-count denominator with regenerative children

## Decision and source

`native_behavior_accepted_cli_scope`, `reusable_published` **only for this one-seed, no-failure mixed profile**. The [pre-run contract](contract.json), SHA-256 `78bc6481ee6da98d25673d327ba917d916f011a9488802bfd8f0fcdd13f358db`, predicted two fixed requests, one fixed start and success, and exclusion of four regenerative children from the fixed count factors. This is one J07 reporting slice, not completion of J07 or a general denominator law.

The accepted parent is `A07.regenerative_relief.1.0.0`, input SHA-256 `fed4f8343d203fc250d8b3508f3f5f9fe76ecbd1a86646d5965531d246b89240`; accepted `J07.var02` supplies the denied fixed-demand mechanism. The child [input](native-input.json), SHA-256 `0b98b8c6816a0923113c1b9e77c5af5493c93104b2bd0dc06bb6552533c1fc3e`, changes exactly `ProblemDescription`, `MissionType`, and `OperationProfile` according to [the exact diff](exact-diff.json), SHA-256 `41ffc87f35b58833e2cbafa17cb495ae2b27be6ac125b7fd4a10daae72a37d06`. A07's two aircraft and 8–16 regenerative period stay unchanged. One feasible fixed demand starts at 20; a three-aircraft demand at 28 is impossible with the two-aircraft pool. The [builder](build.py) is SHA-256 `2a41546382c381c763ec9d2b93282c81c7d14e37e2ca66d9b2cff6fdc040033e`.

The installed SIMLOX manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3` describes regenerative exclusion from fixed mission start/success factors on physical page 553, fixed count reporting on page 566, and estimated regenerative system-time demand on page 568. The dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. These proprietary sources remain local.

## Fresh native run

Run `j07-fixed-regen-v100-20261001-01` used executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`, authenticated session-0 SSH, `Global\SimloxIssue18NativeQueue`, and a before/after active GUI PID 13340 identity guard. [The runner](run_native_ssh.ps1), SHA-256 `dee4e12379857c5ff3865da2681cca8162fd6bd9e5049c601489004667b2af83`, bound the input, parent, contract, builder, checker and executable hashes before and after execution. Import, export, calculation, default JSON report and roundtrip checker all exited zero. All 13 populated source tables roundtripped exactly. Conversion reported zero errors; warnings #108 (logging) and #126 (itemless teaching aircraft) were classified. The ignored raw [closure](runs/j07-fixed-regen-v100-20261001-01/closure.json) SHA-256 is `b4512b7988506dc8ad225c3e3ed1edfd57b5fa42351ee2cf36414617572f890c`; SXO `be3e180ffaa2b668a07a03a1a4cbc4b428ce35aa2b0e696fca30daff41da53de`, event log `8ca7d91c635beaf5bb75e106c8c5dd8450da57a8c229f8763845982edc60c1b6`, and default report `1b6dbafd31e6237c77df6a543be63f8f0715dd54e668dcf9af6eadd7e69070a5`.

The native log shows four regenerative children starting at 8, 10, 12 and 14 and succeeding at 12, 14, 16 and 16. The last child has zero on-station time at the period boundary. `FIXED-OK` is ordered at 19, starts at 20 and succeeds at 24. `FIXED-DENY` is ordered at 27, requests three aircraft, waits with only two available, and cancels at 28.3333 without launch. The 72 half-hour System and Stock bins integrate 18 operating aircraft-hours, no failures, repairs or backorders, and two ready aircraft at hour 36. Compared with A07's accepted parent, the only added operation is one aircraft during hours 20–24; Stock bins are unchanged.

## Native report reconciliation

The installed `Default.sxs`, SHA-256 `1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d`, omits mission-detail tables. [The settings builder](make_report_settings.py), SHA-256 `bc20fb694eec9775ba8bbce6ce643fae52818f18951921324df7a78a9463655d`, enables eight mission flags in ignored local copies and changes the length-prefixed selector. It leaves the installed file untouched. [Child](report_existing_sxo_ssh.ps1) and [A07 parent](report_a07_parent_ssh.ps1) guarded runners, SHA-256 `c4da75bdc02ee87f80c28495f4a63d94594e77a3a984c5a4325200e8152fdd03` and `fdbe15dc54263c0de18ecb560b6afd4595a3b2125567b57279cf1ce7d16d58ea`, generated six report-only exports from sealed SXOs.

| Native total or selector | Requests / starts / successes | Requested / accomplished mission-hours | Requested / accomplished aircraft-hours |
|---|---:|---:|---:|
| Child `FixedMissionResultsTotal`, all | 2 / 1 / 1 | 8 / 4 | 16 / 4 |
| Child `FIXED-OK` | 1 / 1 / 1 | 4 / 4 | 4 / 4 |
| Child `FIXED-DENY` | 1 / 0 / 0 | 4 / 0 | 12 / 0 |
| Child `RegenMissionResultsTotal` | null / 4 / 4 | 8 / 8 | 12 / 14 |

Thus the global `MSTF=MSUF=1/2`, consistent with the native fixed total. Counting all observed successes as fixed requests would incorrectly yield 5/6. The regenerative-only A07 parent has `MSTF=MSUF=0` and no fixed total. The child time factors include the regenerative operation: `MTMF=12/16=0.75` and `STMF=18/28≈0.642857`. The parent regenerative total matches the child regenerative total. `MissionResultsTotal` time fields are 36-hour normalized rates; the raw hours here are from fixed and regenerative detail totals and interval reconciliation.

| Report-only run ID | Closure SHA-256 |
|---|---|
| `j07-all-report-20261001-01` | `c0a3bafa9e7f979c0c925288775cc00efcc89fea3a30b853c0087716ddf7be01` |
| `j07-regenerative-report-20261001-01` | `0cf64fcba0618865fcb152cc92a0a4f5c977d727b553eace365e00119508e2f5` |
| `j07-fixed-ok-report-20261001-01` | `339cdbd40137f88478d2f880a9a7311eda04cb20593adc39cc0d904ec49e009d` |
| `j07-fixed-deny-report-20261001-01` | `b297060bc7c69eb947128ef3c94ed43edb81384cf33285be1fe27c28d1bd172c` |
| `a07-all-report-20261001-01` | `29dbcc48c3652c6699ac9d34a6bece52cc270cd037c515ff876ff65bf835c712` |
| `a07-regenerative-report-20261001-01` | `2d92c8a64803987494b074669053179647bc910452a2afeb02288aaee5e7ff02` |

## Review and limits

[Author read-only replay](validate.py), SHA-256 `6338eb522f3028788667d8bb8bf2dc77a6345ea5cb7845dd728a882864aefc87`, passed 918 checks; its [result](review/author-validation-2026-10-01.json) SHA-256 is `7820510011c35e5282473518488c9e005ffa83aa7eef3094e6cfbea2543f9b76`. The separate [independent reviewer](review/independent_readonly.py), SHA-256 `59f6ba8b340aca4569abcc3247f4f243216110aeb20f3876587a43779552245d`, imported no author implementation and made no native calls. Its [result](review/independent-readonly-2026-10-01.json), SHA-256 `c3cb34af21cadfcddbe6260938a44a171c86f34a335a984be2278ca2d287e7eb`, passed 121/121 checks with bounded GO.

This single deterministic seed has no failures or support-resource competition and only one regenerative period. Regenerative count behavior under failures, mid-mission partial outcomes, unit/group/type aggregation, GUI rendering and cross-engine parity remain unverified. Issue #18 remains open.
