# F04.var02 bounded 43-day stochastic CLI scope signoff — 2026-10-04

**Decision: ACCEPT one bounded fixed-128 replication F04.var02 risk-failure slice for simlox/main.** This is the configured eight-aircraft, two-base 1032-hour teaching fleet with 21 scheduled requests per mission wave at 48-hour spacing. It does not accept all F04 support configurations or close Issue #18. Product main remains separate.

## Frozen lineage and native execution

The direct accepted [F04.var01 input](../F04-var01-deterministic-43day-v1.0.1/native-input.json) SHA-256 is 7b9dfa927ba85c1260d9cbf6d58bae44914ad039a7b3b87b082e1ed04827cc4d; its repeat-A closure is b054ac23c12ae181f299882256cc95308ee7b15de38d31a36aa7895c995b1447 and signoff f7da8657477092954884dfd17fcf681442fffb37df9b2c9d0eb13d91963a4631. The [candidate input](native-input.json) SHA-256 is 33ec12ae0e576969673bcb0e9ccb2ade9bb3799b91e13d734e77950941645cb4, [exact diff](exact-diff.json) eadd2bdb31593272d35c0a68650463f8b4952de37f1ba9598f3ea5d85835926b, and [contract](contract.json) 185ee7bceb23e7fd3f2172e6b76e2eceec4c10911c743a5ae70639bb22217937. The source changes seven parent cells (description, NREPS1→128, TCLEV null→0, System/LRU/SRU FRT0→1,000,000, RISK-MISSION.MFF0→1), then appends two System TOTAL-only replication control rows. Mission schedule, fleet, PM, stocks and resource network are unchanged.

The excluded one-replication mechanism pilot closure is 9629e70787a7c01631bae064e910aef74666f44f5e7e4d8b0496fe8b2499d445. Its first risk mission aborts on a critical LRU fault at h22.4896, then a base backorder, depot spare issue, two-hour transport and repair path occur. The excluded 32-replication variance pilot closure is 67110840ee7a7a7c25c7a866529e8137cbe5f9bd68c84ab862949a4e4f5e12f0 and its analysis is 480fa3881d64afca140b52097afcee5c875b588d9a34405c7355a0176a7a96d9. These pilots select the reporting method and test precision planning; their draws are not added to the fixed-128 acceptance sample.

Two fresh serial guarded session-0 SSH runs preserved active GUI PID13340, verified sshd ancestry and held the host-wide mutex. Repeat A closure SHA-256 is e61172db53cbaf56555ee1be7585284e5e709a72490c0a5d3306fb0da13f8be9; repeat B 3af2e89cbe7a40073cf53cec2e2cd5b088e7491198861eb190b1ea417e108a66. Each completed import, export, calculation, default report, report-only OUTRP export and 31-populated-table exact roundtrip. Converter Errors0/Warnings1/Notes0 contains only reviewed #108; 28/28 local raw files across both runs pass size and SHA seals. The installed Default.sxs SHA-256 1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d was not edited. The local OUTRP-enabled copy SHA-256 6417a4f4ece02e758b4cae90afb674ec93d3c0b3aa730bdb6334df036d746882 changes exactly one N→Y byte and only the reporting export.

## Replication results and precision

Each OUTRP report parses as strict JSON and contains 128 unique Replications IDs/seeds, 128 System TOTAL rows for each unit, and 256 full-horizon SystemResultsReplication rows. First-rep ENLOG is byte-identical across the one-, 32- and 128-rep runs: 63 mission starts, 43 successes, 20 aborts and 27 critical random failures. FMSUC equals 43/63 and the two System NFAIL totals sum to 27. Per-replication means reconcile with ResultSummary; the mean System STACC integral reconciles with the 2064-bin aggregate System report.

The [author replay](author-native-validation-2026-10-04.json) SHA-256 a2c1402c6e5d4b22f29234046098395608d972f9303638f2670bda4b49f5f3d1 and [independent replay](review/independent-verdict.json) independently calculate nominal two-sided 95% Student t intervals directly from the 128 per-replication fields:

| Measure | Mean | Half-width | Predeclared maximum |
| --- | ---: | ---: | ---: |
| Mission success fraction (FMSUC) | 0.672495 | 0.001772 | 0.05 absolute |
| Aircraft operating hours per replication (two-unit STACC × 1032) | 158.807 | 0.930 | 5% of mean = 7.940 |
| Observed failures per replication (two-unit NFAIL) | 25.906 | 0.403 | 10% of mean = 2.591 |

All three gates pass. The [independent replay](review/independent_replay.py) returns GO_BOUNDED, 13,832/13,832 checks; replay SHA-256 c683e305e0f65929d96633784eaa39a9e76eef3087914072d7601ac382c32518 and verdict SHA-256 dfba87aa2fb076a3ca511ddba882243e334988f000a4816979f8a054d8bfd74f. The [static preflight](review/static-review-2026-10-04.md) SHA-256 ed212b7464c717538f210afc8524b343349240d63a160b37e0f4b04243fc7175 cleared the two native runs. The repeat runs' model.log, default report and OUTRP report are byte-identical; they confirm same-seed execution repeatability and are not 256 independent replications. The native ResultSummary RSM fields differ from sample standard errors calculated from per-replication values and are not used as confidence intervals. The default native report contains a trailing comma; replay corrects that narrow parse issue while retaining the sealed raw bytes. The OUTRP report parses without correction.

Aggregate stock and resource ledgers remain descriptive: 51.8125 backordered item-hours, 389.296 booked resource-hours and 30.336 queued resource-hours per replication. The terminal aggregate bin shows seven ready and one unavailable aircraft. No precision claim is made for these support measures. Only the first replication's event timeline is available in ENLOG; later timelines, seed independence, a wider population law, GUI visual parity and cross-engine equivalence are unverified. F04.var03–var05 and Issue #18 remain open.

The [evidence index](evidence-index.json) seals candidate source/reviewer files, 28 accepted native raw files and 26 excluded pilot raw files; bulky SXI/SXO, logs and reports stay local.
