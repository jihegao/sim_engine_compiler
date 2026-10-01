# J04.var04 bounded native thread scope

Status: author pair replay and independent read-only replay passed; PR gates pending. The independent replay made 4,619 checks with zero failures across the four accepted runs and the two excluded runs.

Accepted parent `J04.var03@1.0.0` input SHA-256 `2fa710997450dcd32190145e4df3d6c0e2e81c76b1236e174af0685c0a80c991` is reused byte-for-byte. Only the native calc command changes from `-threads 1` to `-threads 2`. The accepted parent one-thread IDs are `j04-var03-nreps-cap-accepted-20261001-01` and `-02`; fresh two-thread accepted IDs are `j04-var04-thread2-accepted-20261001-02` and `-03`.

Both fresh two-thread runs pass four native steps, GUI coexistence, zero converter errors with classified warnings #108/#211/#126, source/invocation/closure/manifest binding, 14 populated-table business roundtrips, and 11 raw seals each. Their reports and first-only logs are byte-identical to each other and to both accepted one-thread parent runs. ResultSummary has NREP32, four mission fractions0.84375 and four relative errors0.114252679. Seventy-two aligned System/Stock bins reconcile mean 3.5 operating aircraft at h8–10, seven aircraft flight hours, no stock demand, and twelve ready at horizon.

The thread-2 probe `j04-var04-thread2-probe-20261001-01` is excluded. Initial accepted ID `j04-var04-thread2-accepted-20261001-01` completed native steps and 11 raw seals but author validation crashed because the first builder lacked a table helper; it has no validation or manifest and is excluded. Archived original source fingerprints preserve that run's provenance. The corrected pair was run fresh after the source fix.

The publication scope is exact-input report and first-replication-log equality for one versus two native calc threads on this installed executable. Other thirty-one replication event histories/counts, general parallel determinism, performance, other thread counts/seeds, GUI visual behavior and cross-engine parity remain unverified.
