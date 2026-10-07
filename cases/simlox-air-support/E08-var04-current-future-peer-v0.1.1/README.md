# E08.var04 current versus future peer stock — corrected contract snapshot

This v0.1.1 contract classifies two accepted SIMLOX CLI runs without a new native call: E08.var01 ENLAT=Y stocked peer and E08.var03 DLAYL=N scheduled future peer stock. Both direct arms retain ENLAT=Y, DLAYL=N and IMMEDIATE lateral policy. Their complete authored-model difference is the description, BASE-02 opening STSIZ 1→0, and an h9 one-unit DEPOT-01→BASE-02 ItemTransfer with two-hour transit. Stock opening and scheduled transfer co-vary, so this is a bounded source-state contrast, not an isolated timing effect.

The contract pins 37 accepted parent source files with distinct local and Git identities, 16 sealed model/station exports (72 raw, 16 closure, 16 invocation files), six local selector settings, accepted E07/I02 schema donors and the excluded E08.var01 v1.0.0/v1.0.1 diagnostics. It predeclares typed movement and backorder timelines and all 48,684 default/selected report cells across the two direct arms. Historical mate arms serve as integrity context only.

Current peer stock is shipped to BASE-01 at h10 and arrives h10.5. The scheduled future spare reaches BASE-02 at h11, after the h10 BASE-01 shortage; the accepted future arm uses an ordinary repaired item arriving BASE-01 h15.1667. The E08.var03 DLAYL Y/N pair has unchanged physical logs, so it supplies no positive DLAYL effect in this source.

v0.1.0 remains excluded by an independent NO_GO_CONTRACT: it incorrectly claimed package absence at freeze. The root selection receipt only established absence before authoring. This version corrects that historical wording and freezes numerical uncertainty ceilings before implementation.

**Status:** contract-only candidate awaiting fresh independent GO_CONTRACT_ONLY. No new native execution, replay acceptance, GUI claim or publication is conferred by this snapshot. The central publication index is authoritative after publication. Raw SXO/log/report files and proprietary selectors remain local under exact byte seals.
