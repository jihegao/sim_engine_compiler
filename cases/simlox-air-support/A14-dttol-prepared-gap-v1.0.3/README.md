# A14.var02 DTTOL on one half-hour continuous predecessor gap (v1.0.3)

This bounded native CLI case measures DTTOL for one explicit CONTINUOUS dependency. SUPPORT uses two failure-prone TEACH-AIR-01 aircraft, with a third ready as a prepared spare; EXECUTE uses one nonfailing EXEC-AIR-01. The model derives from accepted [A05 prepared-spare behavior](../A05-var02-prepared-spare-probe-v1.0.0/cli-scope-signoff-2026-09-30.md), and its MissionSystem schema is checked against accepted [A11 mixed-type minimum](../A11-mixed-type-minimum-v1.0.0/cli-scope-signoff-2026-09-30.md). A fixed-seed SUPPORT aircraft failure at 9.8829 causes a half-hour suspension and prepared replacement at 10.3829 in every variant. EXECUTE stays scheduled to 11.9.

The [frozen contract](contract.json) was written before five new native runs, explicitly describing earlier [v1.0.0](../A14-dttol-prepared-gap-v1.0.0/README.md), [v1.0.1](../A14-dttol-prepared-gap-v1.0.1/README.md) and [v1.0.2](../A14-dttol-prepared-gap-v1.0.2/README.md) NO-GO diagnostics. The accepted A05 parent input SHA-256 is b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d; A11 schema donor SHA-256 is 4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213. The [exact diff](exact-diff.json) SHA-256 is 2537166e6183b56586914e0c247d4fefdda0991412ade955bb4d9037c140211b. The five source input SHAs are sealed in the contract and native closures.

| Input | DTTOL hours | EXECUTE gap-related suspension | EXECUTE suspended exposure | EXECUTE end |
| --- | ---: | --- | ---: | --- |
| Control | no dependency | none | 0 | success 11.9 |
| Zero | 0 | 9.8829–10.3829 | 0.5 hour | success 11.9 |
| Below | 0.49 | 10.3729–10.3829 | 0.01 hour | success 11.9 |
| Edge | 0.5 | same-time suspend/resume at 10.3829 | 0 | success 11.9 |
| Above | 0.51 | none | 0 | success 11.9 |

SUPPORT alone contributes 0.5 suspended aircraft-hour in every run. The total native suspended exposure is 0.5, 1.0, 0.51, 0.5 and 0.5 aircraft-hours in table order; total operating exposure is 10.9, 10.4, 10.89, 10.9 and 10.9 aircraft-hours. In all dependent variants the native log also emits an hour-8 same-time EXECUTE suspend/resume during simultaneous launch; that transition has no report exposure. All SUPPORT missions succeed at 12; all four aircraft are ready at the end. The [author replay](validate.py) passes 1,483 checks over exact source lineage, five immutable raw closures, 17/18 populated business-row roundtrip, event identities, 32 system and stock bins, failure/preparation/repair exposure, native factors and terminal state. Warnings are #108 (event logging) and two #126 entries for the item-free aircraft types; conversion errors are zero.

The original bulky artifacts remain in ignored local runs/ paths. Each run used session-0 SSH, Global\SimloxIssue18NativeQueue and GUI PID 13340 identity guards. The [case sign-off](cli-scope-signoff-2026-10-01.md) lists immutable run IDs and SHA-256 hashes. To reproduce on the licensed 4700-3 host, run build.py and describe_diff.py as source checks, execute run_native_ssh.ps1 through authenticated session-0 SSH with a fresh RunId for each variant, then run validate.py. Original run IDs cannot be reused.

This is one fixed seed and one prepared half-hour SUPPORT gap. It establishes the observed suspension threshold and successful resumption in this configuration. Other gap lengths, stochastic schedules, absent or failed precedents, multiple precedents, profile dependence, GUI visual content and cross-engine equivalence remain unverified. Issue #18 stays open.
