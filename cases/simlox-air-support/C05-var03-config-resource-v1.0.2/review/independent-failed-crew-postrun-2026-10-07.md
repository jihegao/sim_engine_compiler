# Independent postrun diagnostic: NO_GO for the frozen pair

The sole guarded C05.var03 v1.0.2 invocation stopped after the crew arm. **The frozen positive contract is false for this observed native trace, and the radio arm was never started.** Preserve the original run as a failed diagnostic; do not reuse it as acceptance for the pair or rerun either reserved ID.

## Sealed provenance

- Crew run `c05-var03-v102-crew-ssh-20261007-01`: closure SHA `7e64959f168a24b3c7311b33f68c9fa14c44bec80a8202dc5047d9dba329bb3a`; failure seal SHA `900e3a93757811307eed29011a4b8cd237b92cf1da68b6029bdccf553974266d`; invocation SHA `3a8ca0eebb86bc2cd02cb1ba0c12069b8f4a199927ee5ac65e5939dfb622eccc`.
- All 13 closure raw SHA/size seals, all 15 failure-seal file SHA/size records, and all 77 manifest source hashes before/after and on disk agree. Approval and actual SSH preflight hashes in the closure equal their saved files. The radio run directory is absent.
- Import, export, independent roundtrip check, calc and JSON report completed in order with exit 0. Four native children were recorded in session 0, with protected GUI preserved at every step. The final behavior check exited 1. The exact authored 24 row-containing tables round-tripped. Calc logged Errors 0, Warnings 4, Notes 0 with only #108 Control and #2053 Item records 1–3. The resulting SXO and default report are substantive, not four-byte placeholders.

## Native counterexample and checker failure

At h7, aircraft `<TEACH-AIR-01,0>` and `<TEACH-AIR-01,1>` each passed a one-unit MISSION-CREW availability test and booked one unit. Both assigned bookings were deallocated **at h7**, during reconfiguration. The configured `<TEACH-CONF-A,0>` and `<TEACH-CONF-B,1>` then launched together at h8, with each native mission/task line explicitly displaying `MISSION-CREW 0`; mission success and completion occurred at h10. The h10 deallocation lines say `mission operation: 0`, so they do not prove a hidden held unit. ResourceResults has zero used occupancy in every bin and ResourceResultsTotal reports `NRMA=0`, `NRMO=0`. This directly contradicts the frozen crew-arm requirement that each configured aircraft gets crew1 during the mission.

The frozen author validator returned `NO_GO`, 1 check, with bare `AssertionError`. Its report oracle counts the two h7 `allocated to mission assigned: 1` lines as starts, but counts four `deallocated from ... mission` lines as ends: the two h7 assignment releases plus two zero-quantity h10 operation releases. Its start/end count assertion fails before field-by-field checks. Correcting that checker would make the diagnostic more informative but cannot change the observed positive-gate failure.

The independent diagnostic script SHA `09ecb78785684e27582d66cbe996110659f45cebf5a7421724d15b309c6e929f` produced deterministic LF verdict SHA `2f8658f1fc082db6065e1edf4ba6516db83d29d8a36f8fad3a29007903455ade` on two runs. It independently reconciled the six report tables' **5,210 cells** to the actual mission, system, stock and zero-occupancy resource events: 1 description, 11 summary, 2,880 system, 1,152 stock, 1,152 resource and 14 resource-total cells. This is a diagnostic consistency result, not a pass of the frozen positive pair.

The opening stock had `<TEACH-LRU-A,0,0>` and `<TEACH-LRU-B,0,2>`. At h7 each type had one demand and its opening item was taken; stock for both types fell to zero. Separate physical base aircraft 0 and 1 each had one reconfiguration fit from h7 to h7.33333, followed by configured A and B preparation and launch. No stock return or backorder is logged before h36, and both terminal depot levels remain zero. Both item demand lines end in `from pos <TEACH-AIR-01,BASE-01,0>`: that suffix is a position index, so those lines alone do **not** establish an item-type-to-aircraft serial edge. The diagnostic retains every observed ID and does not infer unlogged serial continuity.

## Recovery boundary

A new, separately frozen read-only counterexample package may cite these immutable bytes and bounded observations. It must keep v1.0.2 positive acceptance `NO_GO`, state the radio arm was untested, and distinguish the validator's premature assertion from the native absence of held crew. Testing a different mechanism or input requires a new contract, distinct run IDs, fresh static and SSH preflight review, and separate authorization under the execution plan. No claim follows about general CBSID resource inheritance, alternate seeds or GUI behavior.
