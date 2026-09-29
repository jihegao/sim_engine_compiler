# D02.var01 traditional LRU OPHOURS long-gap: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed traditional installed-LRU OPHOURS run across a 30-hour no-flight interval. This is a bounded D02.var01 result, not a general failure-clock algorithm claim or the full D02 boundary matrix.

## Source and native run

The accepted [D01 installed-LRU parent](../D01-installed-lru-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) input SHA-256 is `eb57ef7bdb9829241303d3827c10ef957e6bb5e8f4f5f6034bb6f5dc603b3b93`. The [D02.var01 input](native-input.json) SHA-256 is `9e6d264330c6f7b41752ed8b0c09a32ac45089cec9ec823ad5e3367ce7f348e2`. The [exact parent diff](parent-diff.json), SHA-256 `77da6e2a52a325346dab3c76f359cfa643c82786884c5d14191c61e3a53fce66`, changes four tables: the description label; `Control.SIMPE/RCEND` 36→60; both `ResultCollection.RCEND` values 36→60; and the third `OperationProfile.STIM` 32→52. The other 27 parent tables are unchanged. `System.FRT` and `Item.FRT` remain 300000 per million `OPHOURS`; the installed LRU, local spare, repair settings, seed and first two missions are unchanged. The [contract](contract.json) freezes the hypothesis.

The installed SIMLOX 2017 manual, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, and accepted D01 parent provide the traditional FRT/OPHOURS source boundary. Native behavior below is established by the run. Neither proprietary source is uploaded.

Native child run ID `d02-var01-traditional-op-v100-ssh-20260930-01` used session-0 SSH, host-wide `Global\SimloxIssue18NativeQueue`, and the active GUI PID 13340 guard. Import, export, calculation, report and roundtrip checker all exited zero. All 18 source row-containing tables roundtripped exactly, including three all-null placeholder rows. Conversion had **zero errors and one warning**, #108 for event logging. Raw artifacts remain in ignored local `runs/`.

| Child raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `327d5620678a09b75ab92e2bbd6b7936cb2e9d3b437eac980be9800e2230ee94` |
| `closure.json` | `fdb0c93c2a59313392587378665115baa26cb23de01e48d543b56eaa33abfbb8` |
| `model.log` | `1c0d3a05fb18c408bcba2502fb022fcd69871741935e2c269c941428a266ba54` |
| `report-raw.json` | `4c8c00b67ec1fbdd5be3570eb87072c34ed4c46434d1910cfec5c98372e99fe8` |

## Observed comparison and review

The accepted D01 control and extended child both log one traditional failure of installed `TEACH-LRU-01` at 9.8829 during the first mission. The child issues local spare item #0 at 10 for failed installed item #1; the system removes and fits the item during 10–10.5, and item #1 undergoes direct repair during 10.25–11.25 before returning to stock. The second mission succeeds at 22. The log contains no failure during the 22–52 no-flight interval: the aircraft is ready through hour 51 and spends 51–52 in mission preparation. The delayed third mission starts at 52 and succeeds at 54. The 120 half-hour system bins total `NFAIL=1` and `NREPT=1`; stock reports one demand and no backorder; one aircraft is ready at the hour-60 stop. The parent has the same first failure and second-mission outcome, with its third mission at 32–34.

The [author replay](review/author-traditional-validation-2026-09-30.json) passed **67/67** checks, SHA-256 `c6162c26195d964a07378ea42d9ba919e9837bb71e58fc37a343df26d91673ef`; its [validator](validate_traditional.py) SHA-256 is `307851f50b5a2c2e894ec174c445205ac23209f0e214fa227828147a87534bc2`. A separate reviewer wrote a [standard-library-only read-only replay](review/independent_traditional_readonly.py), SHA-256 `73dd3dc03319a35ea5abc7fdeeafd056041281b98b31daba5c86d5efc8eaebed`, without importing the author validator. Its [102/102 result](review/independent-traditional-2026-09-30.json), SHA-256 `a1f7344950b11450376f4655739e1097a41cca7517fb6cd59c73ed4f5883e79d`, agrees with the exact delta, sealed raw/source evidence, traditional LRU path and gap/mission report ledgers.

One quiet interval under one seed is consistent with the configured OPHOURS exposure but does not prove a general engine clock rule. Traditional `Item`/`ItemFailureRate` `CALHOURS` or `MISSIONS` negative acceptance, zero-exposure behavior, other seeds, GUI visual content and cross-engine equivalence remain unverified. The GUI identity and active session were guarded, but visual content was not sampled. Issue #18 stays open.
