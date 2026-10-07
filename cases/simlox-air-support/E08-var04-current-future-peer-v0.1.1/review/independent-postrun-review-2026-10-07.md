# Independent E08.var04 read-only replay — GO_BOUNDED

The separate standard-library replay is `independent_replay.py`, 52,475 bytes,
SHA-256 `558993694997f82db32b8fd85598f3c251a2f304eac61dfaa27184c019a43dc7`.
Its deterministic LF verdict is `independent-verdict.json`, 1,137 bytes,
SHA-256 `f75b63103a4d9d34e4fff73180f21a0957c0dfe24b5a8fdd6b0a1986cf3f47ad`.
The replay was run from the accepted source and raw files; it imported no author checker,
did not invoke SIMLOX, and changed no accepted source or run file. A second read-only
execution emitted exactly the verdict bytes already saved.

## Bounded evidence

- Corrected frozen contract `b95349ff646d5faaf2d754cce2624e39735bdf772865f294a93828140596bad3` and its separately preserved v0.1.0 NO_GO history were rehashed.
- 198 contract local byte pins, 49 published Git blob identities, all 104 files of 16 accepted runs, 16 invocation/closure seals, exact GUI/SSH0/mutex historical metadata, and 49 row-containing authored-table roundtrip identities passed. The old invocation/steps do **not** record each child PID and session; their recorded session-zero SSH ancestry and integer-zero exits are the historical limit.
- The authored models differ in exactly `ProblemDescription.PDESC` and `StockAllocation(BASE-02).STSIZ` 1→0, plus one future `ItemTransfer` row. The two compared direct arms keep `ENLAT=Y`, `DLAYL=N`, `LSRUL=IMMEDIATE`, schedule, mission, seed, and horizon. Co-varying stock and transfer inputs prevent an isolated causal claim.
- Both raw logs independently reconstruct the h10 BASE-01 shortage, current peer ID1 take/typed request/transport h10→10.5, versus future depot ID0 scheduled transfer h9→11, depot wait h10→14.1667 and ordinary depot→BASE-01 item shipment h14.1667→15.1667. The mounted failed item's native-generated repair ID is kept distinct from the opening stock IDs. Physical stock, nominal stock, and backorder station intervals end nonnegative with zero terminal backorders.
- Expected values for every cell in the two four-table default reports and six ten-table selected-station reports were constructed from source rows, report definitions, and typed event ledgers. All **48,684** cells matched, including complete metadata, instance names, IDs, nulls, counts, System and Stock interval occupancy, mission results, Item station totals, and summary fields. Direct-system `StockTotalResults` uses BASE-01 demand; propagated peer/depot demands stay in station `ItemResults`.
- For Item `ROS`/`ROST`, the manual's demand-based definition and the typed demand/wait edges yield null in a no-demand interval, zero for immediately served demand, and one for positive wait. A served wait is credited to its demand-start interval. `WT`/`WTT` use the closed wait duration; `WTS` remains null when there is no positive wait. No candidate cell supplies an expected value.
- Whole-bin zero/integer state, discrete counts, strings, identity and null are exact. Fractional cells use the half-last-displayed-decimal uncertainty of contributing non-source event edges divided by 0.5 h or 36 h, or source-defined mission denominators, plus at most 5e-7 serialization. Each computed bound must stay below its frozen class ceiling. Source-determined whole and half-hour edges are exact. Unknown formulas fail closed. Twelve in-memory semantic mutations were rejected, including an event-bin fraction changed by 0.0002 that is below the broad class ceiling but above its specific propagated bound, tiny whole-bin/count changes, null/zero switches, an elapsed change, an instance tag, wrong stock ID/station, and missing opening stock.
- The accepted E08.var03 DLAYL context mate has a byte-identical physical log and only its description cell differs in the report. This supports no positive DLAYL timing inference.

## Development and limits

The review-only passing draft before provenance, route, and mutation additions is preserved read-only as `excluded-development-draft-replay-2026-10-07.py`, 30,771 bytes, SHA-256 `ac90194c7439323e2a9b764f322fe253d45fce99f23a997e078e2ad9539ea484`. Earlier exploratory mismatch outputs were displayed only in tool transcripts; exact standalone stdout files and first-draft hashes are unavailable and are not reconstructed. The corrections were source/manual/typed-event interpretations: availability as one minus unavailable state, per-mission system count versus flight duration, selector reports matched to their own native arm, and the manual's immediate-service versus no-demand stock metric distinction. The frozen contract and numeric ceilings were not changed.

This is a retrospective reuse of accepted runs. It establishes the two printed physical traces and complete report reconciliation within those fixed sources. It is not a fresh control experiment, a general lateral-support priority law, a positive DLAYL effect, or proof of unrecorded per-child PID/session identities.
