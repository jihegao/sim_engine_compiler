# E05 local LRU repair, restock and reissue: CLI scope sign-off (2026-09-29)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one local LRU repair loop whose repaired item is issued on a later demand. The pinned run produced three complete cycles, all of which are traced. This does not accept a shortage, late repair/backorder, remote supply, reorder, resource competition or PM case.

## Frozen source and execution

This case derives from accepted E01 input SHA-256 `84ca1828f3669d2c91c9d826cae3187e0968ae9f8fed602d97155d2e82e99931`. The [parent diff](parent-diff.json) changes only `ProblemDescription`, `System.FRT` and `Item.FRT`, raising the equal traditional `OPHOURS` rates from 300000 to 450000 per million. The E05 input SHA-256 is `ee294a430382811a1e0f1d058fbca4fd1df6f7f0646300c671ccc1bcbe0055ca`; the predeclared [contract](contract.json) SHA-256 is `4bf1082eafa9b9e5c4578fe19ebd0106ed5c91f2e3d45aa7fc554b41e13baea2`. Installed SIMLOX executable SHA-256 is `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`; installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.

Native run `e05-v100-ssh-20260929-01` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` mutex and active GUI PID 13340 guard. Import, export, calculation and report export exited zero; 20 row-containing source tables, including three all-null placeholder tables, roundtripped identically. Conversion had zero errors and only logging warning 108. Sealed invocation SHA-256 is `a5e5b85421c0d25d1779fad20da0eb7acbb98ea03a347591436157930704bbac`; closure SHA-256 is `e75836bcd99ba838d4ef247973794a2bf38fbddd4904d69337d631ba983d01ef`. Raw evidence stays in the ignored local `runs/e05-v100-ssh-20260929-01/` directory.

## Observed material loop

| Wave | Critical LRU failure | Demand and local issue | Removed item reaches repair | System ready | Repaired item restocked |
| --- | ---: | --- | ---: | ---: | ---: |
| 1 | 9.25527 | 9.75527: issue spare instance 0 for failed instance 1 | 9.92193 | 10.2553 | instance 1 at 10.9219 |
| 2 | 21.9597 | 22: issue **repaired instance 1** for failed instance 2 | 22.1667 | 22.5 | instance 2 at 23.1667 |
| 3 | 33.3079 | 33.8079: issue **repaired instance 2** for failed instance 3 | 33.9746 | 34.3079 | instance 3 at 34.9746 |

Every failure aborts its scheduled mission. Each system replacement performs explicit 10-minute `<REMOVE>` and 20-minute `<REPLACE>` in sequence; the removed item starts one-hour direct `ItemRepair` at removal completion. The stock event ledger shows on hand `1→0→1` in each cycle, without backorders. In particular, instance 1 completed repair and returned to stock at 10.9219, well before it was issued on the second demand at 22. The extra third cycle also completed before the 36-hour horizon.

The raw event log SHA-256 is `3ed9e6a5fc2d66dd8eb5fa4f111bc3baa127dfbfc40aadac639ed55e7f8701f8`; the raw JSON report SHA-256 is `fcf9a124546e77fb96871b5bf4b5e111774c00616bfed69c19ad7f1b6c08b4bf`. The report contains 72 aligned half-hour system and stock intervals, three failures, three completed repairs, three stock demands, zero backorders, terminal ready aircraft and mission success fraction zero. The fractional repair-occupancy bins integrate to 1.5 aircraft-hours of system replacement. The accepted E01 control had one failure/repair/demand and two successful missions; E05 adds two of each and all three missions abort. Exact item identity and transition times come from the event log; the report provides aggregate intervals and rounds times differently.

## Review and limits

The [author replay](review/author-native-validation-2026-09-29.json) passed 79 source-bound checks with no differences. Its source SHA-256 is `214528530d144d18148059c322037ba555e8552e8ec0925981e39460fa89a4bc`, and its report SHA-256 is `182bf4fd2ba1b5019b6777e0f614481675d3436b7579952159f1310c80503cd7`. A separate reviewer performed [static prelaunch review](review/static-review-2026-09-29.md) and [independent read-only native replay](review/independent-native-review-2026-09-29.json), with no differences. The independent report SHA-256 is `ad7801108647a3cb0790a0d93abf85f45c5613377b0dcfb7e6f58d0c59026936`. The independent replay checked frozen inputs, three-table delta, every sealed raw hash, SSH/GUI records, three identity-matched material loops, report totals and the E01 control.

The contract required at least two failures and complete tracing of any additional failure. Three occurred on this executable and all three are covered. The rate and seed do not prescribe the failure count or timestamps on other executables. GUI visual content was not sampled.
