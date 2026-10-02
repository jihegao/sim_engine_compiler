# I01.var01 resource-only POINT selection

This bounded native case tests whether `Control.APID` selects one of two
`ResourceAllocation` POINTs held in the same model. It extends the accepted
C01 v1.0.2 two-person P-CREW preparation case. The earlier I01.var01
stock-only case is a separate published slice; combined Stock, Resource and
Maintenance allocation selection is still unverified.

## Frozen source contrast

The accepted C01 capacity-two source has SHA-256
`a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c`.
This package adds two `AIR_ZERO` ResourceAllocation rows at BASE-01 with
P-CREW and P-OTHER quantities zero. Existing `AIR_BASIC` quantities remain
P-CREW2 and P-OTHER0. The selected source SHA-256 is
`ac35a07731c629e16ba6bd83183eaca9c244161c2cc05a07cf7b2127cd52bbc5`;
the zero source is
`f9b3032405accccfcd3bf6906fa82b9b1755036dc2d9865eface0f8d543c9371`.
The two sources differ only in `Control.APID` and ProblemDescription. The
two-P-CREW `SubTaskResource` demand, station, aircraft, schedule, seed and
36-hour horizon stay fixed. StockAllocation has no rows;
MaintenanceAllocation has no authored table. `exact-diff.json` records this
source delta with SHA-256
`9fe6b5ef06f2d878b73d21a08f4039aa0cb24f6fef5fa962603be75d00829fee`.

## Native observation

Two fresh session-0 SSH runs were serialized by
`Global\SimloxIssue18NativeQueue` and preserved GUI PID13340. Both converted
with zero errors, produced valid SXO and report output, round-tripped 20
row-containing authored tables (17 substantive tables plus three all-null
placeholders), and sealed 12 raw artifacts per arm. Both runs emit only the
expected warning #108 for the event log and #126 for a system with no items.

With APID `AIR_BASIC`, the h7 INSPECT step requests and books two P-CREW,
works for ten minutes, releases both at h7.16667, then SERVICE completes
at h7.5. The mission flies h8–10 and succeeds. ResourceResults reports
average utilization `NRUM=2/3` in the h7–7.5 bin: two people for ten minutes
are 20 person-minutes. With APID `AIR_ZERO`, the same request fails to find
two crew, no resource is booked or work performed, and the mission cancels
at h7.58333. ResourceResults has `NR=0`, `NRUM=0`, and `NRW=2` for h7–7.5.
SystemResults records no flight in this arm. Both aircraft are ready at the
36-hour horizon; the result summary shows mission success fraction 1 versus 0.

This result supports only APID selection of ResourceAllocation POINTs for
the C01 preparation demand at BASE-01. It does not establish combined
stock/resource/maintenance POINT selection, E01 LRU repair resources,
station routing, StationVariant, GUI visual behavior or cross-engine parity.

## Reproduction

Run `build.py` and `describe_diff.py` to verify frozen inputs. On the
licensed Windows host, call `run_native_ssh.ps1` through session-0 SSH for
each arm with new immutable run IDs. The runner checks source fingerprints,
the host mutex, GUI identity, native conversion/report output and the
roundtrip before sealing raw files. `validate.py` replays authored assertions;
the independent checker under `review/` replays the evidence without importing
the authored implementation. `evidence-index.json` lists all local run IDs,
hashes and raw seals. Native raw artifacts stay local and Git-ignored.
