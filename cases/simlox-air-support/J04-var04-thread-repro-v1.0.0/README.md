# J04.var04 one-versus-two native thread reproducibility

This bounded case uses accepted `J04.var03@1.0.0` seed-01 input byte-for-byte (SHA-256 `2fa710997450dcd32190145e4df3d6c0e2e81c76b1236e174af0685c0a80c991`). The native calc invocation changes only `-threads 1` to `-threads 2`. The model retains NREPS32, TCLEV0.09, the Poisson formation-count mechanism, twelve aircraft, the same mission schedule, half-hour reports, and hour-36 horizon.

Two accepted one-thread J04.var03 parent runs and two fresh accepted two-thread runs all produce byte-identical JSON reports and first-replication event logs. The two-thread runs passed guarded session-0 SSH import/export/calc/report, zero converter errors, 14 populated-table business roundtrips, source-bound validation, and 22 raw SHA-256 seals. Each report shows NREP32, MTMF/MSTF/MSUF/STMF0.84375, relative errors0.114252679, 72 aligned System/Stock bins, 3.5 mean operating aircraft at hour 8–10 (inferred 1.75 two-aircraft formations), seven aircraft flight hours, no stock demand, and terminal twelve ready.

Independent read-only replay passed 4,619 checks with zero failures, including 44 recomputed raw seals across the four accepted one- and two-thread runs. The replay script and verdict are under `review/`.

One source-sealed thread-2 diagnostic probe is excluded. The first attempted accepted run completed all four native steps and sealed 11 raw files, but its author validator crashed because the initial builder omitted a table helper. That run has no validation or manifest and is excluded. Its original source files are archived under `review/superseded-first-acceptance/`. The corrected accepted pair uses fresh IDs 02/03.

The exact-input comparison supports native report and first-only ENLOG equality for this installation, seed, and one-versus-two-thread CLI setting. ENLOG does not expose the other thirty-one replication event histories/counts. It does not establish general parallel determinism, performance scaling, other thread counts, seeds, GUI visual behavior, or cross-engine parity.

The runner requires authenticated session-0 SSH, the host-wide Issue #18 mutex, exact source/manual/dictionary/executable hashes, and preservation of GUI PID 13340. Raw `runs/` stays local and ignored; `evidence-index.json` records accepted and excluded IDs with SHA-256 seals. The proprietary manual and dictionary are pinned but not included.
