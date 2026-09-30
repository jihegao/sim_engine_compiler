# A14 DTTOL paired stochastic-schedule diagnostic (v1.0.1)

**Decision: NO-GO for the frozen five-run DTTOL comparison.** This version extended EXECUTE to hour 11.9 so it overlapped the control's SUPPORT suspension at 11.1325–11.6325. The four dependent variants changed the failure allocation: SUPPORT did not suspend in any of them, so DTTOL had no measured SUPPORT gap. None is published as tolerance behavior.

The accepted A05 prepared-spare parent input SHA-256 is b7ca5f4d6152e2c166b1ba7fe8b41246c24782a50d56b2bcc773f86f176d3f4d. The contract, exact diff (SHA-256 00586ff7f8f013fde4b06e779a651fd256a339c02e3b85327f950898480a7bc8), five immutable inputs and the session-0 SSH runner were frozen before execution. All five native runs completed import, export, calculation, report and exact 16/17-table source-row roundtrip with zero converter errors and warnings #108/#126 under the host-wide mutex and GUI PID 13340 guard.

| Variant | DTTOL hours | Native run ID | Closure SHA-256 | Event-log SHA-256 |
| --- | ---: | --- | --- | --- |
| Control | no row | a14-dttol-control-v101-20261001-01 | 8559dff4e0aef5fd4cb97bf2b3589d7fa7bebc3a1bd58baa78d969ac35143221 | c1c1c63c8df9d1e5e2b53b421aba7f9776149782aca1d5786d54da58850f55b0 |
| Zero | 0 | a14-dttol-zero-v101-20261001-01 | 78d0f316530432542425271774c62b37814836059e853cacb9b99bde35f1c5d4 | 8e1d69363e22f7381db5023353d0ac49d8bce41ef1c03590d9a939ee2d078670 |
| Below | 0.49 | a14-dttol-below-v101-20261001-01 | 3725cf95b1115fbf5da400e61767a9e272fd5839926ab7077f6c04a03f71b4d2 | 8e1d69363e22f7381db5023353d0ac49d8bce41ef1c03590d9a939ee2d078670 |
| Edge | 0.5 | a14-dttol-edge-v101-20261001-01 | 7aa024b70b35138038b267debbcc25cf176ed1d3055870a2145262f93cbe7c2e | 8e1d69363e22f7381db5023353d0ac49d8bce41ef1c03590d9a939ee2d078670 |
| Above | 0.51 | a14-dttol-above-v101-20261001-01 | 19a0e1acee59d182739bab879ef1ccb759199a6a63fc2d8c59a60d56a4f690b3 | 8e1d69363e22f7381db5023353d0ac49d8bce41ef1c03590d9a939ee2d078670 |

Control: EXECUTE briefly suspends and immediately substitutes aircraft at 9.8829, succeeds at 11.9; SUPPORT suspends at 11.1325, resumes after a prepared replacement at 11.6325 and succeeds at 12. Each dependent input: EXECUTE has an immediate substitution at 11.1325, while SUPPORT remains continuously active and succeeds at 12. The four dependent event logs are byte-identical despite different DTTOL values. The failed stochastic comparability gate prevents attribution. Raw runs remain ignored locally. The [v1.0.2 probe](../A14-dttol-prepared-gap-v1.0.2/README.md) separates SUPPORT and EXECUTE aircraft types so only SUPPORT carries the failure clock.
