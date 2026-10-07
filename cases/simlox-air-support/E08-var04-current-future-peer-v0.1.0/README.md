# E08.var04 current versus future peer stock — contract snapshot

This v0.1.0 contract classifies two accepted SIMLOX CLI runs without a new native call: E08.var01 ENLAT=Y stocked peer and E08.var03 DLAYL=N scheduled future peer stock. Both direct arms retain ENLAT=Y, DLAYL=N and IMMEDIATE lateral policy. The authored difference is the description, BASE-02 opening STSIZ 1→0, and an h9 one-unit DEPOT-01→BASE-02 ItemTransfer with two-hour transit. Stock opening and scheduled transfer co-vary, so this is a bounded contrast of source states rather than an isolated timing experiment.

The contract pins both parent packages, all 16 sealed model/station exports (72 raw, 16 closure, 16 invocation files), six local selector settings, accepted E07/I02 schema donors, and excluded v1.0.0/v1.0.1 diagnostics. It predeclares typed movement and backorder timelines plus every cell in the default and three selected station reports: 24,342 cells per direct arm, 48,684 in total. Historical mate arms are integrity context only.

Current peer stock is physically shipped to BASE-01 at h10 and arrives h10.5. The scheduled future spare reaches BASE-02 at h11, after the h10 BASE-01 shortage; the accepted future arm uses an ordinary repaired item arriving BASE-01 h15.1667. Both arms have their own source/event-derived report ledger. The accepted E08.var03 DLAYL Y/N pair has unchanged physical logs and no positive DLAYL distinction in that source.

**Status:** contract-only candidate awaiting independent GO_CONTRACT_ONLY. No new native execution, replay acceptance, GUI claim, or publication is conferred by this snapshot. The central publication index is authoritative after publication. Raw SXO/log/report files and proprietary selectors remain local and are referenced by exact byte seals.
