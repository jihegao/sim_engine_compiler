# E08.var01: immediate lateral support, ENLAT on/off

This bounded native SIMLOX case establishes a genuine lateral source before the I02.var08 no-lateral OUT case is attempted. It derives from the accepted E07 item-specific FAST route. `BASE-01` has a demand and no spare; peer `BASE-02` has one spare; both have ordinary upstream support from `DEPOT-01`, which has one spare. The peers join `LAT-01`; `LateralSupport` uses `IMMEDIATE`, `DLAYL=N`, and 0.5-hour shipment; `StationLateralSupport` explicitly defines the BASE-02 to BASE-01 link. The matched input pair differs only in `Control.ENLAT=Y/N` and description.

The source requests half-hour `ITEM` results and sets `Item.TRACK=Y`. These two observation settings are necessary to export per-station `ItemResults`. Sealed v1.0.0 and v1.0.1 diagnostic runs showed the same event-log route effect but lacked one or both settings; they remain local and are not this published version.

## Native result

Both v1.0.2 inputs roundtrip all 24 populated source tables exactly, calculate with zero conversion errors, and produce nonempty output. Session-0 SSH runners serialized work with `Global\SimloxIssue18NativeQueue` and preserved GUI PID 13340.

| Observation | ENLAT=Y | ENLAT=N |
|---|---|---|
| h10 replacement source for BASE-01 | BASE-02 physical LRU ID 1 | DEPOT-01 physical LRU ID 0 |
| BASE-01 replacement arrival | h10.5, 0.5-hour lateral leg | h11, one-hour ordinary leg |
| BASE-01 backorder | one half-hour ItemResults bin | two half-hour ItemResults bins |
| Aircraft ready after fit | h10.8333 | h11.3333 |
| Peer BASE-02 | Sends ID 1 at h10; depot replenishes it with ID 0 at h11 | Keeps initial spare on hand |
| Terminal h36 | BASE-01 on-hand 0, BASE-02 1, DEPOT-01 1, no station backorders | Same |

`ItemResults.STSZ` remains nominally 1 at the donor/depot while `STOHA` falls to zero during shipment. The native log tracks physical item identities; the half-hour station reports track inventory and backorder occupancy. Both arms retain one aborted first mission and two later successes; mission bins and summary are equal. System and stock bins record the shorter waiting and readiness interval in the enabled arm.

## Reproduce and limits

Run `build.py` and `describe_diff.py` to check the frozen source and exact delta. `run_native_ssh.ps1` requires session-0 SSH, the installed manual/dictionary/executable fingerprints, the fixed GUI identity, and an available host-wide queue. It writes immutable raw runs under ignored `runs/`. `report_native_ssh.ps1` exports three selected station views per SXO using local SXS settings. `validate_native.py` checks the sealed raw evidence; the separate `review/independent_readonly.py` replays it without importing author logic. `evidence-index.json` records local run IDs, raw SHA-256 hashes, source hashes, and report-setting hashes without publishing proprietary or bulky native artifacts.

This case proves one IID, one stocked lateral peer, one upstream depot, `IMMEDIATE`, `DLAYL=N`, and a fixed half-hour lateral route. EXTENDED/ADJACENT, delayed lateral, competing peers, GUI rendering, and cross-engine parity remain unverified. It does not itself establish I02.var08's no-lateral response to an OUT transfer; that case needs a child of this accepted geometry.
