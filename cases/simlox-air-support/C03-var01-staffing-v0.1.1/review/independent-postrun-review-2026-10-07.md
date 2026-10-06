# C03.var01 staffing read-only replay — 2026-10-07

**Decision: GO_BOUNDED** for the three accepted, fixed-seed C03 CLI runs reused by the corrected v0.1.1 contract. My separately authored standard-library `independent_replay.py` passed **18,091/18,091 checks**, including all **15,630 report cells** (six tables, 5,210 cells per arm), with zero failures. It ran twice with identical LF-only verdict bytes.

## Provenance and source

- Corrected contract SHA-256 `652f886c5d22eaaa20f605812695055586af81209b99682d357112a8c903043f` matches. The original v0.1.0 contract and its independent NO_GO memo remain sealed; the corrected accepted evidence-report hash matches the published/local parent. The accepted C03 contract and original independent review also match.
- All 16 accepted C03 tracked source files match their published Git bytes, except the declared `.gitignore` local CRLF (8-byte) versus Git LF (7-byte) identity; both hashes and sizes match the contract. C02/A03 prerequisite inputs and installed SIMLOX manual match their literals.
- Each final staffing-2, staffing-1 and staffing-0 input, closure and invocation matches its pin. All **33/33** original raw file SHA-256 and size seals pass. Each invocation identifies SSH session 0, `sshd.exe` ancestry, the global native mutex and the same responsive GUI PID 13340/session 1/start timestamp. Each has ordered import/export/calc/report steps, exit 0, a substantial SXO, converter Errors 0/Warnings #108 and #126/Notes 0, and exact populated authored-cell roundtrip across 20 row-containing tables. Native-added empty-table rows are all-null placeholders.
- Comparing all authored tables, columns, instances, rows and cells across arms finds only the shared `ResourceAllocation.RQTY` at AIR_BASIC/P-CREW/BASE-01: **2→1→0**. Description, seed, two aircraft and mission definition are the same.

## Physical and report replay

The same mission ID allocates aircraft IDs 0 and 1 at h7.5 in each arm. With two crew, both aircraft book and work concurrently h7.5–8; the mission launches h8 and succeeds/completes h9. With one crew, ID0 works h7.5–8, releases before ID1 books h8, ID1 works h8–8.5, and the mission launches h8.5 and succeeds/completes h9.5. With zero crew, both requests fail, neither task performs, the mission cancels and both waits stop at h8.5; neither aircraft launches. The logs show both aircraft ready again at the respective end times.

I constructed all 72 half-hour SystemResults, StockTotalResults and ResourceResults rows for each arm from these windows, including null fields, then compared every cell. I separately checked the 11 ResultSummary fields, 14 ResourceResultsTotal fields and description. Stock is equal across arms, with no demand or backorder. Crew busy integrals are one person-hour in each positive arm and zero in the zero-crew arm; request-wait integrals are 0, 0.5 and 2 aircraft-request-hours respectively. The corresponding 36-hour ResourceResultsTotal means match. `ResourceResults.NRA` was checked as reported; it was not inferred as the complement of busy workers.

This is a reclassification of three already accepted native runs. It does not establish a general aircraft priority, resource scheduling, deadline or zero-capacity rule, and does not cover new replications, equipment, shifts, GUI-only behavior or cross-engine parity. No native/GUI process was called and no accepted source/raw artifact was changed.

Replay script SHA-256: `4e92a1c9f9ff1647e18fb5bc3baf5bbc85f162554a31a6be2e8d8caf84d53c38`. Deterministic LF verdict SHA-256: `45f4b5fc80ca5ac5700428ad03346d21fa3158d816f81f0d5a0eaa9a15a6095e`.
