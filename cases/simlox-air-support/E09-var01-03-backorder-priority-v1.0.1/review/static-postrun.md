# E09 v1.0.1 independent static post-run review

**Decision: bounded GO for the three-arm, one-seed native CLI contrast.** The accepted observation is the first repaired LRU's allocation between two concurrently outstanding depot requests. The v1.0.0 native run remains an excluded full-contract diagnostic because its default report had no station-selected ItemResults rows.

## Provenance and execution

- Contract SHA-256 `1b5ef8c1312ab444fdc40b697707cffa52515fbf2c12149b52187707b6ecaa57` pins accepted E12.var02 parent and the excluded v1.0.0 closure `be24943da186459639a309db3ed3bd8f9bd29744ce3f6fd636f793c7bdfea28e`. From v1.0.0 to v1.0.1, each arm changes only `Item.TRACK` and `ResultCollection.ITEM`; the model event log is byte-identical to its respective diagnostic arm. Among v1.0.1 arms, FIFO to priority changes depot `Station.BOPRI` plus description; priority to disabled changes `Control.ENBOP` plus description.
- Native closure SHA-256 `77634d18e49988534adff6f3a9ef9c32bcb85f12e65da5293fc2c088bcddc295` seals 32 raw files and twelve completed import/export/calc/report steps. Selected-report closure SHA-256 `3c7069c1abe090b2edff7cf6e846c44ec6c7126b025da67217e6d4690d750c17` seals 20 raw files and nine completed arm-by-station exports. I checked every listed raw file against its byte count and SHA-256; both closures have stable before/after source hashes, session-0 SSH ancestry, the global mutex and preserved GUI PID 13340/session 1. The report-only closure pins the native closure, all three SXOs and all three station selectors.
- All native arms converted with zero errors and usable output. The selected reports contain 72 half-hour ItemResults rows for the specified `TEACH-LRU-01` at each of DEPOT-01, BASE-01 and BASE-02. The DEPOT-01 selector is byte-identical to the accepted J08 full item-position selector; BASE-01 and BASE-02 use the same layout with only the station token changed.

## Physical and report contrast

- The earlier ordinary BASE-01 replenishment request reaches the depot at h10.7579; the BASE-02 aircraft-blocking backorder arrives at h11.5. Both remain outstanding before repaired physical LRU ID1 returns at h14.9246.
- FIFO sends ID1 to BASE-01 at h14.9246, arriving h15.9246; repaired ID2 is sent to BASE-02 at h15.6667, arriving h16.6667. Priority reverses these destinations: ID1 goes to BASE-02 and ID2 to BASE-01. Disabled matches FIFO at the event-log byte level. The v1.0.1 log hashes are FIFO/disabled `4cead7756818d7d8d613375e0efa62a74f8dbb9ac0e25fef9b1d5fa7f6f3cc30` and priority `3504cb92c93b82c61bc2709d1468769bef5513954ccb6152c791365c36806367`.
- Selected ItemResults distinguish nominal size `STSZ`, physical on-hand `STOHA` and station backorders `NBO`. At h15.5–16, BASE-01's FIFO `STOHA` is positive but priority is zero; BASE-02's priority `NBO` is already declining while FIFO remains at one. All nine 72-row station ledgers were checked against the piecewise physical events by the separately authored independent replay, **3,390/3,390 GO**, verdict SHA-256 `00c66bab6d5920f0d86facf4b494fa655fba7087f64fc0594ef313fc7401c86a`. The author report checker separately reports **1,380/1,380**, result SHA-256 `4e487d4a834f30da580b1cae833d0c982d2fec708bfd4de7663a18adc3218692`.

## Limits and readiness

This is a single fixed seed, two bases, one depot, one item type and one first-inbound allocation. It does not establish a general priority tie-breaker or a mission-success effect. `StockTotalResults.NBO` is not the sum of all station-level `ItemResults.NBO` here; the station-selected rows and physical log support the stock claim. No GUI-only or cross-engine behavior is inferred.

The frozen closures and separate independent replay are sufficient for a bounded CLI sign-off. Publication still needs its generated evidence index and scoped index entry; those files are outside this review's edit scope.
