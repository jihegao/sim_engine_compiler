# I01.var01 ResourceAllocation POINT selection — bounded CLI sign-off, 2026-10-02

**Decision:** Accept only the observed APID selection of `ResourceAllocation`
POINTs in the accepted C01 two-P-CREW preparation model. The earlier I01.var01
stock-only case and this resource-only case do not together prove simultaneous
StockAllocation, ResourceAllocation and MaintenanceAllocation selection. Keep
Issue #18 open.

## Frozen lineage and execution

- Accepted C01 v1.0.2 capacity-two parent source SHA-256
  `a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c`.
  This case adds two AIR_ZERO resource rows with zero P-CREW/P-OTHER capacity.
  Selected source SHA-256
  `ac35a07731c629e16ba6bd83183eaca9c244161c2cc05a07cf7b2127cd52bbc5`;
  zero source SHA-256
  `f9b3032405accccfcd3bf6906fa82b9b1755036dc2d9865eface0f8d543c9371`.
  The arms differ only by `Control.APID` and description. Exact diff SHA-256
  `9fe6b5ef06f2d878b73d21a08f4039aa0cb24f6fef5fa962603be75d00829fee`;
  pre-run contract SHA-256
  `9bc3491966f1c47a428d459b38ad298812407332f7d45e442b3a91d89b401df6`.
- Installed manual physical pp397–399 and 407–414 describes the
  SubTaskResource request and SPECIAL ResourceAllocation POINT. Independent
  pre-run static review approved the two-arm diagnostic.
- Two serial guarded session-0 SSH runs preserved GUI PID13340 and completed
  import, export, calc, JSON report and roundtrip checker. Each converted
  with zero errors and warnings #108/#126 only, produced valid SXO/report,
  round-tripped 20 row-containing source tables (17 substantive, three
  all-null placeholders), and sealed 12 local raw files. Author replay passed
  24/24 checks; independent read-only replay passed 9,607/9,607 checks and
  returned `GO_BOUNDED_RESOURCE_APID_SELECTION`.

## Observed boundary

Both arms request two P-CREW for INSPECT at h7. Under AIR_BASIC, two crew
are booked before work, released at h7.16667, SERVICE ends h7.5, and the
mission flies h8–10 successfully. ResourceResults h7–7.5 records `NR=2`,
`NRUM=2/3`, consistent with 20 person-minutes. Under AIR_ZERO, the request
fails with zero crew; no booking or positive work occurs and the mission
cancels h7.58333. ResourceResults h7–7.5 records `NR=0`, `NRUM=0`, `NRW=2`;
SystemResults has no flight. All 72 Resource/System/Stock bins per arm and
terminal aircraft ready1 were independently checked.

This establishes resource POINT/APID selection at one station and seed with
a C01 preparation demand. There are no authored stock or maintenance
allocation business rows. Combined allocation selection, E01 replacement
resources, station routing, StationVariant, GUI visual behavior and
cross-engine parity remain unverified.
