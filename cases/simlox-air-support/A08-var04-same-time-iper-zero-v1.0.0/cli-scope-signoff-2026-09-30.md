# A08.var04 IPER=0 simultaneous missions: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one `ITYPE=RANDOM`, fixed `IQTY=3`, empty `IQTYD`, `IDISP=RANDOM` profile at `STIM=8` with `IPER=0`, three available aircraft and a fixed two-hour mission template. The aggregate 32-replication report and separately frozen 32-seed one-replication event matrix support different claims.

## Source and frozen model

The accepted [A08.var01 parent](../A08-var01-fixed-count-random-time-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `df7ecf0549fc8b1a506095194b97dac810afc395a76b4c478cfe43eec1838920`. The [A08.var04 child](native-input.json) SHA-256 is `bae76ba5a88871129fb2669a8d04744745b8831f11d0dec96c7594d621793485`; the [exact diff](exact-diff.json) SHA-256 is `2e90ec2b0590622672dd5b8208460c90d442f91d56b79c72bf27f7c18426d1c2`. `OperationProfile.IPER` changes 12→0; `ProblemDescription.PDESC` changes only a label. The other 29 tables are identical. `Control.NREPS=32`, `RSEED=1`, `STIM=8`, `ITYPE=RANDOM`, `IQTY=3`, empty `IQTYD`, `IDISP=RANDOM`, three aircraft, the fixed two-hour mission template, zero failure rate, hour-36 horizon and half-hour reporting remain. The [initial contract](contract.json) SHA-256 is `161e8e3caf53bb314e042e525bd544c9222d273de7c187881f8080ff9d8ee77c`.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Physical PDF page 274 describes zero `IPER` as initiating all missions at the same time. The native evidence below tests this exact input. The proprietary manual remains local.

## Sealed native evidence

Aggregate run `a08-var04-same-time-v100-ssh-20260930-01` completed import, export, calculation, JSON report and exact 13-populated-source-table roundtrip. Conversion errors were zero; warnings #108 (event logging) and #126 (teaching aircraft with no items) are classified. `ResultSummary.NREP=32`; 72 aligned half-hour system and stock bins cover hours 0–36. Integrated mean `NSYMO=6` aircraft mission-operation hours per replication, terminal readiness is three aircraft, and failure, repair and stock-demand ledgers are zero. Its event log exposes only one replication: three missions start simultaneously at hour 8 and succeed and complete at hour 10. It does not reveal the other 31 timelines.

The [matrix contract](contract-seed-matrix-v1.json) SHA-256 is `af3663db3757d21de3c765804e7d28e0703ed857f0cff3a7f681ba89f3f62476`; the [seed manifest](seed-matrix-v1.json) SHA-256 is `ce971c2ff06054752e272feffd4e78a09102052e0903c6cb64b8cdd155af1348`; the generator SHA-256 is `3cb251644a73b2c9698fa55698c638e7ce5b5037dc34c8250a4490b094baa23c`. Each generated seed input changes only `Control.NREPS` 32→1, `RSEED` 1→the explicit seed number, and one provenance label. Matrix run `a08-var04-seed-matrix-v100-ssh-20260930-02` completed 32 serial native runs and 160/160 import/export/calc/report/check steps under the host-wide queue. Every seed has zero conversion errors, the same classified warnings, exact 13-table roundtrip, a one-replication report with 72 bins, six aircraft operation-hours, three ready aircraft at end, no cancellation/failure/repair and zero stock demand/backorder. All 96 logged mission starts occur at hour 8 and complete successfully at hour 10. The seed-1 timeline matches the aggregate run's exposed timeline.

| Run and artifact | SHA-256 |
| --- | --- |
| aggregate `invocation.json` | `462ba2add1795b32e2060b081c39a06d5aee457b1941c0f2bc911db79432892a` |
| aggregate `closure.json` | `cdc14d679a458bb9f942a9fc64f2a4aeb59bfb83a82fce0c8dcab2129f598b14` |
| aggregate `model.log` | `a029ec2cc17ebfd8acf3a488459f48d118affdd2c318a9937718c99f42f87206` |
| aggregate `report-raw.json` | `507bbd2d4e4dad9973518c2d46d24ee3aa0338016e1aa38331410467f555f926` |
| matrix `invocation.json` | `ac91d132cbdd2ef170ce421c7caefbc58634e297d1bf951b2b10ee2c1a432743` |
| matrix `closure.json` | `1ca334ba93c0c6f395e34247e9893eddf5c89d86881a66f518f2e2f96ae295dc` |
| matrix `steps.json` | `c31f9a8b91a68f499951966db385575431d9dadf56880a6fdd501bd016ca04e6` |

Both invocations record session-0 SSH with `sshd.exe` ancestry, host mutex `Global\\SimloxIssue18NativeQueue`, GUI PID 13340/session 1 and its original start identity. Every native step checks that GUI identity. Source hashes match before and after. The aggregate closure seals 12 raw files and the matrix closure seals 353. Installed executable SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`. The parser normalizes native JSON trailing commas only in memory; byte seals use untouched raw files. The matrix SSH entry used the archived [wrapper](ssh-wrapper-used.ps1), SHA-256 `1df220c6ebd9d277ffeddb683474db6d242814c1a64881e67f1d156662abfd2c`, which marks startup and invokes the source-hashed guarded runner; it contains the original host path.

## Review and limits

The [author validator](validate_same_time.py), SHA-256 `77df6999776052a59b119ab1e8c20dda87bc136d5fbf45826098091d059570a5`, passes [1,566/1,566 checks](review/author-same-time-validation-2026-09-30.json), SHA-256 `a5d07d299602b27f172ba38b08921550da99b2744902788bbd9b57e76031fe93`. A [separate read-only reviewer](review/independent_same_time_readonly.py), SHA-256 `0ed5dad3e1b79505f014e1c556c98ae853804814bab63d84ffa028648917d9b2`, passes [1,124/1,124 checks](review/independent-same-time-2026-09-30.json), SHA-256 `83209ec0c33a937bebc69bdc0d8e0ad2a6847ed2ac541c251b81beb00ca4058b`, without importing author validation. Its JSON was byte-identical on a second replay. The independent replay links each child mission to a distinct aircraft and reconciles event-derived occupancy with every system report bin. Native raw files remain in ignored local `runs/`; generated seed inputs in ignored `seed-inputs/` reproduce byte-identically from the generator and manifest.

Reproduce source and exact delta with `python build.py`, `python describe_diff.py`, and `python build_seed_matrix.py` from this package; replay sealed local runs with `python validate_same_time.py` and `python review/independent_same_time_readonly.py`. Use a fresh versioned ID for new native execution. This finding covers one fixed quantity of three, one zero-period start at hour 8, three available aircraft and 32 explicit seeds. The seed matrix is a convenience set and does not establish all possible seeds or other zero-period profiles. GUI visual content and cross-engine equivalence remain unverified. Issue #18 remains open.
